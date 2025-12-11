#!/usr/bin/env python3
"""
Open-AutoGLM 混合方案 - Web 远程监控版 v1.1
可以在电脑浏览器上查看手机执行情况

优化内容:
- 更好的 UI 界面
- 实时状态更新
- 手动控制功能
- 截图压缩优化
"""

import os
import sys
import base64
import requests
import time
import json
import re
import threading
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from PIL import Image
except ImportError:
    print("请安装 Pillow: pip install pillow")
    sys.exit(1)

# ============== 配置 ==============
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-seed-1-6-vision-250815")
HELPER_URL = os.getenv("AUTOGLM_HELPER_URL", "http://localhost:8080")
WEB_PORT = int(os.getenv("AUTOGLM_WEB_PORT", "8888"))

# 全局状态
state = {
    "running": False,
    "task": "",
    "step": 0,
    "max_steps": 25,
    "status": "空闲",
    "thought": "",
    "action": "",
    "screenshot": "",
    "logs": [],
    "connected": False
}

def log(msg):
    """添加日志"""
    ts = time.strftime("%H:%M:%S")
    state["logs"].append(f"[{ts}] {msg}")
    state["logs"] = state["logs"][-100:]
    print(msg)

# ============== 手机控制器 ==============
class Controller:
    def __init__(self):
        self.url = HELPER_URL
        self.width = 1080
        self.height = 2400
    
    def check(self):
        try:
            r = requests.get(f"{self.url}/status", timeout=3)
            if r.status_code == 200:
                state["connected"] = r.json().get('accessibility_enabled', False)
                return state["connected"]
        except:
            pass
        state["connected"] = False
        return False
    
    def screenshot(self):
        try:
            r = requests.get(f"{self.url}/screenshot", timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get('success') and data.get('image'):
                    # 压缩图片
                    img_data = base64.b64decode(data['image'])
                    img = Image.open(BytesIO(img_data))
                    self.width, self.height = img.size
                    
                    # 缩小并压缩
                    if img.width > 720:
                        ratio = 720 / img.width
                        img = img.resize((720, int(img.height * ratio)), Image.LANCZOS)
                    
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            log(f"截图失败: {e}")
        return None
    
    def screenshot_full(self):
        """获取完整截图用于 AI 分析"""
        try:
            r = requests.get(f"{self.url}/screenshot", timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get('success') and data.get('image'):
                    img_data = base64.b64decode(data['image'])
                    img = Image.open(BytesIO(img_data))
                    self.width, self.height = img.size
                    return img
        except:
            pass
        return None
    
    def tap(self, x, y):
        try:
            r = requests.post(f"{self.url}/tap", json={'x': x, 'y': y}, timeout=5)
            return r.status_code == 200 and r.json().get('success')
        except:
            return False
    
    def swipe(self, x1, y1, x2, y2, duration=500):
        try:
            r = requests.post(f"{self.url}/swipe", 
                json={'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'duration': duration}, timeout=10)
            return r.status_code == 200 and r.json().get('success')
        except:
            return False
    
    def input_text(self, text):
        try:
            r = requests.post(f"{self.url}/input", json={'text': text}, timeout=5)
            return r.status_code == 200 and r.json().get('success')
        except:
            return False
    
    def back(self):
        try:
            r = requests.post(f"{self.url}/back", timeout=5)
            return r.status_code == 200 and r.json().get('success')
        except:
            return False
    
    def home(self):
        try:
            r = requests.post(f"{self.url}/home", timeout=5)
            return r.status_code == 200 and r.json().get('success')
        except:
            return False

# ============== AI 模型 ==============
class AIModel:
    def __init__(self):
        self.api_key = DOUBAO_API_KEY
        self.api_url = DOUBAO_API_URL
        self.model = DOUBAO_MODEL
    
    def analyze(self, img, task, width, height, history=None):
        buf = BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        
        prompt = f"""分析手机屏幕，完成任务：{task}

屏幕尺寸：{width}x{height}，左上角(0,0)

可用操作：
- tap: 点击 {{"x":数字,"y":数字}}
- input: 输入 {{"text":"文字"}}
- swipe: 滑动 {{"x1":起点x,"y1":起点y,"x2":终点x,"y2":终点y}}
- back: 返回
- home: 主页
- done: 完成

返回JSON格式：{{"action":"操作名","params":{{参数}},"thought":"说明"}}

例如点击屏幕中间：{{"action":"tap","params":{{"x":{width//2},"y":{height//2}}},"thought":"点击中间"}}

只返回一个JSON："""

        try:
            r = requests.post(
                f"{self.api_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                    ]}],
                    "max_tokens": 300,
                    "temperature": 0.1
                },
                timeout=60
            )
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content'].strip()
                # 解析 JSON
                if content.startswith("```"):
                    content = "\n".join(content.split("\n")[1:-1])
                match = re.search(r'\{[^{}]*\}', content)
                if match:
                    return json.loads(match.group())
        except Exception as e:
            log(f"AI错误: {e}")
        return {"action": "wait", "params": {}, "thought": "分析失败"}

# ============== 全局实例 ==============
ctrl = Controller()
ai = AIModel()

# ============== 任务执行 ==============
def run_task(task):
    global state
    state["running"] = True
    state["task"] = task
    state["step"] = 0
    state["status"] = "运行中"
    log(f"▶ 开始: {task}")
    
    history = []
    
    for step in range(1, state["max_steps"] + 1):
        if not state["running"]:
            log("⏹ 已停止")
            break
        
        state["step"] = step
        state["status"] = f"步骤 {step}/{state['max_steps']}"
        
        # 截图
        img = ctrl.screenshot_full()
        if not img:
            log(f"步骤{step}: 截图失败")
            time.sleep(2)
            continue
        
        # 更新预览
        preview = ctrl.screenshot()
        if preview:
            state["screenshot"] = preview
        
        # AI 分析
        result = ai.analyze(img, task, ctrl.width, ctrl.height, history)
        action = result.get('action', 'wait')
        params = result.get('params', {})
        thought = result.get('thought', '')
        
        state["thought"] = thought
        state["action"] = f"{action} {params}"
        log(f"步骤{step}: {thought} → {action}")
        
        history.append({'action': f"{action}", 'thought': thought})
        
        # 执行
        if action == 'done':
            state["status"] = "✅ 完成"
            log("✅ 任务完成")
            break
        elif action == 'tap':
            ctrl.tap(int(params.get('x', 0)), int(params.get('y', 0)))
        elif action == 'swipe':
            ctrl.swipe(int(params.get('x1', 0)), int(params.get('y1', 0)),
                      int(params.get('x2', 0)), int(params.get('y2', 0)))
        elif action == 'input':
            ctrl.input_text(params.get('text', ''))
        elif action == 'back':
            ctrl.back()
        elif action == 'home':
            ctrl.home()
        
        time.sleep(1.5)
    
    state["running"] = False
    if state["step"] >= state["max_steps"]:
        state["status"] = "⚠️ 步数限制"

# ============== Web 界面 ==============
HTML = '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoGLM 控制台</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui;background:#0d1117;color:#c9d1d9;min-height:100vh}
.header{background:#161b22;padding:15px 20px;border-bottom:1px solid #30363d}
.header h1{font-size:20px;color:#58a6ff}
.container{display:flex;gap:20px;padding:20px;max-width:1400px;margin:0 auto}
@media(max-width:900px){.container{flex-direction:column}}
.left{flex:0 0 360px}
.right{flex:1;min-width:0}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:15px;margin-bottom:15px}
.card h3{font-size:14px;color:#8b949e;margin-bottom:10px}
.screen{width:100%;border-radius:6px;background:#000;cursor:pointer}
.status-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.stat{background:#21262d;padding:10px;border-radius:6px}
.stat-label{font-size:11px;color:#8b949e}
.stat-value{font-size:14px;margin-top:4px;word-break:break-all}
.connected{color:#3fb950}.disconnected{color:#f85149}
input[type=text]{width:100%;padding:10px;border:1px solid #30363d;border-radius:6px;background:#0d1117;color:#c9d1d9;font-size:14px}
.btns{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
button{padding:8px 16px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}
.btn-primary{background:#238636;color:#fff}
.btn-danger{background:#da3633;color:#fff}
.btn-secondary{background:#21262d;color:#c9d1d9;border:1px solid #30363d}
.logs{height:300px;overflow-y:auto;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:10px;font-family:monospace;font-size:12px}
.log{padding:3px 0;border-bottom:1px solid #21262d;color:#8b949e}
.controls{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.ctrl-btn{padding:12px;background:#21262d;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;cursor:pointer}
.ctrl-btn:hover{background:#30363d}
</style>
</head><body>
<div class="header"><h1>🤖 AutoGLM 远程控制台</h1></div>
<div class="container">
<div class="left">
<div class="card">
<h3>📱 手机屏幕 (点击刷新)</h3>
<img id="screen" class="screen" onclick="refresh()" alt="等待截图">
</div>
<div class="card">
<h3>🎮 手动控制</h3>
<div class="controls">
<button class="ctrl-btn" onclick="action('home')">🏠 主页</button>
<button class="ctrl-btn" onclick="action('back')">◀ 返回</button>
<button class="ctrl-btn" onclick="refresh()">🔄 刷新</button>
</div>
<div class="controls" style="margin-top:8px">
<button class="ctrl-btn" onclick="swipe('up')">⬆ 上滑</button>
<button class="ctrl-btn" onclick="swipe('down')">⬇ 下滑</button>
<button class="ctrl-btn" onclick="swipe('left')">⬅ 左滑</button>
</div>
</div>
</div>
<div class="right">
<div class="card">
<h3>📊 状态</h3>
<div class="status-grid">
<div class="stat"><div class="stat-label">连接状态</div><div id="conn" class="stat-value disconnected">检查中...</div></div>
<div class="stat"><div class="stat-label">运行状态</div><div id="status" class="stat-value">空闲</div></div>
<div class="stat"><div class="stat-label">当前思考</div><div id="thought" class="stat-value">-</div></div>
<div class="stat"><div class="stat-label">当前操作</div><div id="action" class="stat-value">-</div></div>
</div>
</div>
<div class="card">
<h3>🚀 任务控制</h3>
<input type="text" id="task" placeholder="输入任务，如：打开淘宝搜索蓝牙耳机">
<div class="btns">
<button class="btn-primary" onclick="start()">▶ 开始任务</button>
<button class="btn-danger" onclick="stop()">⏹ 停止</button>
<button class="btn-secondary" onclick="document.getElementById('task').value=''">清空</button>
</div>
</div>
<div class="card">
<h3>📋 运行日志</h3>
<div id="logs" class="logs"></div>
</div>
</div>
</div>
<script>
const $ = id => document.getElementById(id);
function update() {
  fetch('/api/state').then(r=>r.json()).then(d=>{
    $('status').textContent = d.status;
    $('thought').textContent = d.thought || '-';
    $('action').textContent = d.action || '-';
    if(d.screenshot) $('screen').src = 'data:image/jpeg;base64,' + d.screenshot;
    $('logs').innerHTML = d.logs.map(l=>'<div class="log">'+l+'</div>').join('');
    $('logs').scrollTop = $('logs').scrollHeight;
    $('conn').textContent = d.connected ? '✅ 已连接' : '❌ 未连接';
    $('conn').className = 'stat-value ' + (d.connected ? 'connected' : 'disconnected');
  });
}
function start() {
  const task = $('task').value.trim();
  if(!task) return alert('请输入任务');
  fetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({task})});
}
function stop() { fetch('/api/stop', {method:'POST'}); }
function refresh() { fetch('/api/screenshot'); }
function action(a) { fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:a})}); }
function swipe(dir) {
  const params = {up:{x1:540,y1:1600,x2:540,y2:800}, down:{x1:540,y1:800,x2:540,y2:1600}, left:{x1:900,y1:1200,x2:200,y2:1200}};
  fetch('/api/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:'swipe', params:params[dir]})});
}
setInterval(update, 1000);
update();
</script>
</body></html>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == '/api/state':
            self.json_response(state)
        elif self.path == '/api/screenshot':
            s = ctrl.screenshot()
            if s: state["screenshot"] = s
            ctrl.check()
            self.json_response({"ok": bool(s)})
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length).decode()) if length else {}
        
        if self.path == '/api/start':
            task = body.get('task', '')
            if task and not state["running"]:
                threading.Thread(target=run_task, args=(task,), daemon=True).start()
            self.json_response({"ok": True})
        elif self.path == '/api/stop':
            state["running"] = False
            log("⏹ 用户停止")
            self.json_response({"ok": True})
        elif self.path == '/api/action':
            a = body.get('action')
            p = body.get('params', {})
            if a == 'home': ctrl.home()
            elif a == 'back': ctrl.back()
            elif a == 'swipe': ctrl.swipe(p.get('x1',540), p.get('y1',1600), p.get('x2',540), p.get('y2',800))
            time.sleep(0.5)
            s = ctrl.screenshot()
            if s: state["screenshot"] = s
            self.json_response({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()
    
    def json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def main():
    print("=" * 50)
    print("  AutoGLM 远程控制台 v1.1")
    print("=" * 50)
    
    if not DOUBAO_API_KEY:
        print("\n❌ 请配置 DOUBAO_API_KEY")
        sys.exit(1)
    
    # 获取 IP
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "localhost"
    
    print(f"\n📡 模型: {DOUBAO_MODEL}")
    print(f"🔗 Helper: {HELPER_URL}")
    print(f"\n🌐 在电脑浏览器打开:")
    print(f"   http://{ip}:{WEB_PORT}")
    print(f"\n按 Ctrl+C 停止服务\n")
    
    ctrl.check()
    log(f"服务启动: http://{ip}:{WEB_PORT}")
    
    server = HTTPServer(('0.0.0.0', WEB_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")

if __name__ == "__main__":
    main()
