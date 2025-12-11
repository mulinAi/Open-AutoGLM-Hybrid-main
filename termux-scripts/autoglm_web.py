#!/usr/bin/env python3
"""
Open-AutoGLM 混合方案 - Web 远程监控版
可以在电脑浏览器上查看手机执行情况
"""

import os
import sys
import base64
import requests
import time
import json
import threading
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

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
agent_state = {
    "running": False,
    "task": "",
    "step": 0,
    "max_steps": 20,
    "status": "空闲",
    "thought": "",
    "action": "",
    "screenshot_base64": "",
    "logs": []
}

def add_log(msg):
    """添加日志"""
    timestamp = time.strftime("%H:%M:%S")
    agent_state["logs"].append(f"[{timestamp}] {msg}")
    if len(agent_state["logs"]) > 100:
        agent_state["logs"] = agent_state["logs"][-50:]
    print(msg)

# ============== 手机控制器 ==============
class PhoneController:
    def __init__(self, helper_url=HELPER_URL):
        self.helper_url = helper_url
    
    def check_connection(self):
        try:
            resp = requests.get(f"{self.helper_url}/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('accessibility_enabled', False)
        except:
            pass
        return False
    
    def screenshot(self):
        try:
            resp = requests.get(f"{self.helper_url}/screenshot", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') and data.get('image'):
                    return data['image']  # 返回 base64
        except Exception as e:
            add_log(f"截图失败: {e}")
        return None
    
    def tap(self, x, y):
        try:
            resp = requests.post(f"{self.helper_url}/tap", json={'x': x, 'y': y}, timeout=5)
            return resp.status_code == 200 and resp.json().get('success')
        except:
            return False
    
    def swipe(self, x1, y1, x2, y2, duration=500):
        try:
            resp = requests.post(f"{self.helper_url}/swipe", 
                json={'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'duration': duration}, timeout=10)
            return resp.status_code == 200 and resp.json().get('success')
        except:
            return False
    
    def input_text(self, text):
        try:
            resp = requests.post(f"{self.helper_url}/input", json={'text': text}, timeout=5)
            return resp.status_code == 200 and resp.json().get('success')
        except:
            return False
    
    def back(self):
        try:
            resp = requests.post(f"{self.helper_url}/back", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def home(self):
        try:
            resp = requests.post(f"{self.helper_url}/home", timeout=5)
            return resp.status_code == 200
        except:
            return False

# ============== 视觉模型 ==============
class DoubaoVisionModel:
    def __init__(self):
        self.api_key = DOUBAO_API_KEY
        self.api_url = DOUBAO_API_URL
        self.model = DOUBAO_MODEL
    
    def analyze_screen(self, image_base64, task):
        prompt = f"""你是一个手机自动化助手。用户的任务是：{task}

请分析当前屏幕截图，决定下一步操作。

返回 JSON 格式：
- action: tap, swipe, input, back, home, done, failed
- params: 操作参数
- thought: 思考过程

示例：
{{"action": "tap", "params": {{"x": 540, "y": 1200}}, "thought": "点击搜索框"}}
{{"action": "done", "params": {{}}, "thought": "任务已完成"}}

只返回 JSON。"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            }],
            "max_tokens": 500
        }
        
        try:
            resp = requests.post(f"{self.api_url}/chat/completions", headers=headers, json=body, timeout=60)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content'].strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1])
                return json.loads(content)
        except Exception as e:
            add_log(f"模型调用失败: {e}")
        return {"action": "failed", "params": {}, "thought": "调用失败"}

# ============== Agent ==============
controller = PhoneController()
model = DoubaoVisionModel()

def run_task(task):
    """在后台线程运行任务"""
    global agent_state
    
    agent_state["running"] = True
    agent_state["task"] = task
    agent_state["step"] = 0
    agent_state["status"] = "运行中"
    add_log(f"开始任务: {task}")
    
    for step in range(1, agent_state["max_steps"] + 1):
        if not agent_state["running"]:
            add_log("任务已停止")
            break
        
        agent_state["step"] = step
        agent_state["status"] = f"步骤 {step}/{agent_state['max_steps']}"
        
        # 截图
        add_log(f"步骤 {step}: 截图...")
        screenshot_b64 = controller.screenshot()
        if not screenshot_b64:
            add_log("截图失败，重试...")
            time.sleep(2)
            continue
        
        agent_state["screenshot_base64"] = screenshot_b64
        
        # 分析
        add_log(f"步骤 {step}: 分析屏幕...")
        result = model.analyze_screen(screenshot_b64, task)
        
        action = result.get('action', 'failed')
        params = result.get('params', {})
        thought = result.get('thought', '')
        
        agent_state["thought"] = thought
        agent_state["action"] = f"{action} {params}"
        add_log(f"思考: {thought}")
        add_log(f"操作: {action} {params}")
        
        # 执行
        if action == 'done':
            agent_state["status"] = "✅ 完成"
            add_log("任务完成!")
            break
        elif action == 'failed':
            agent_state["status"] = "❌ 失败"
            add_log("任务失败")
            break
        elif action == 'tap':
            controller.tap(params.get('x', 0), params.get('y', 0))
        elif action == 'swipe':
            controller.swipe(params.get('x1', 0), params.get('y1', 0),
                           params.get('x2', 0), params.get('y2', 0))
        elif action == 'input':
            controller.input_text(params.get('text', ''))
        elif action == 'back':
            controller.back()
        elif action == 'home':
            controller.home()
        
        time.sleep(1.5)
    
    agent_state["running"] = False
    if agent_state["step"] >= agent_state["max_steps"]:
        agent_state["status"] = "⚠️ 达到步数限制"

# ============== Web 服务器 ==============
HTML_PAGE = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoGLM 远程监控</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 20px; color: #00d4ff; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
        .card { background: #16213e; border-radius: 12px; padding: 20px; }
        .card h2 { color: #00d4ff; margin-bottom: 15px; font-size: 18px; }
        .screenshot { width: 100%; max-width: 400px; border-radius: 8px; border: 2px solid #333; }
        .status { padding: 10px; background: #0f3460; border-radius: 8px; margin-bottom: 10px; }
        .status-label { color: #888; font-size: 12px; }
        .status-value { font-size: 16px; margin-top: 5px; }
        .logs { height: 300px; overflow-y: auto; background: #0a0a15; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 12px; }
        .log-line { padding: 2px 0; border-bottom: 1px solid #222; }
        input[type="text"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background: #0f3460; color: #fff; font-size: 16px; margin-bottom: 10px; }
        button { padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; margin-right: 10px; margin-bottom: 10px; }
        .btn-start { background: #00d4ff; color: #000; }
        .btn-stop { background: #ff4757; color: #fff; }
        .btn-refresh { background: #2ed573; color: #fff; }
        .connected { color: #2ed573; }
        .disconnected { color: #ff4757; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AutoGLM 远程监控</h1>
        
        <div class="grid">
            <div class="card">
                <h2>📱 手机屏幕</h2>
                <img id="screenshot" class="screenshot" src="" alt="等待截图...">
                <p style="margin-top:10px; color:#888;">点击图片可刷新</p>
            </div>
            
            <div class="card">
                <h2>🎮 控制面板</h2>
                
                <div class="status">
                    <div class="status-label">连接状态</div>
                    <div id="connection" class="status-value disconnected">检查中...</div>
                </div>
                
                <div class="status">
                    <div class="status-label">运行状态</div>
                    <div id="status" class="status-value">空闲</div>
                </div>
                
                <div class="status">
                    <div class="status-label">当前思考</div>
                    <div id="thought" class="status-value">-</div>
                </div>
                
                <div class="status">
                    <div class="status-label">当前操作</div>
                    <div id="action" class="status-value">-</div>
                </div>
                
                <input type="text" id="task" placeholder="输入任务，如：打开淘宝搜索蓝牙耳机">
                <div>
                    <button class="btn-start" onclick="startTask()">▶ 开始任务</button>
                    <button class="btn-stop" onclick="stopTask()">⏹ 停止</button>
                    <button class="btn-refresh" onclick="refreshScreen()">🔄 刷新屏幕</button>
                </div>
                
                <h2 style="margin-top:20px;">📋 运行日志</h2>
                <div id="logs" class="logs"></div>
            </div>
        </div>
    </div>
    
    <script>
        function updateState() {
            fetch('/api/state')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('status').textContent = data.status;
                    document.getElementById('thought').textContent = data.thought || '-';
                    document.getElementById('action').textContent = data.action || '-';
                    
                    if (data.screenshot_base64) {
                        document.getElementById('screenshot').src = 'data:image/png;base64,' + data.screenshot_base64;
                    }
                    
                    const logsDiv = document.getElementById('logs');
                    logsDiv.innerHTML = data.logs.map(l => '<div class="log-line">' + l + '</div>').join('');
                    logsDiv.scrollTop = logsDiv.scrollHeight;
                });
        }
        
        function checkConnection() {
            fetch('/api/check')
                .then(r => r.json())
                .then(data => {
                    const el = document.getElementById('connection');
                    if (data.connected) {
                        el.textContent = '✅ 已连接';
                        el.className = 'status-value connected';
                    } else {
                        el.textContent = '❌ 未连接';
                        el.className = 'status-value disconnected';
                    }
                });
        }
        
        function startTask() {
            const task = document.getElementById('task').value.trim();
            if (!task) { alert('请输入任务'); return; }
            fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task: task})
            });
        }
        
        function stopTask() {
            fetch('/api/stop', {method: 'POST'});
        }
        
        function refreshScreen() {
            fetch('/api/screenshot');
        }
        
        document.getElementById('screenshot').onclick = refreshScreen;
        
        setInterval(updateState, 1000);
        setInterval(checkConnection, 5000);
        checkConnection();
        updateState();
    </script>
</body>
</html>'''

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 禁用日志
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        
        elif self.path == '/api/state':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(agent_state).encode())
        
        elif self.path == '/api/check':
            connected = controller.check_connection()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"connected": connected}).encode())
        
        elif self.path == '/api/screenshot':
            screenshot = controller.screenshot()
            if screenshot:
                agent_state["screenshot_base64"] = screenshot
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": bool(screenshot)}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length else '{}'
        
        if self.path == '/api/start':
            data = json.loads(body)
            task = data.get('task', '')
            if task and not agent_state["running"]:
                threading.Thread(target=run_task, args=(task,), daemon=True).start()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        
        elif self.path == '/api/stop':
            agent_state["running"] = False
            add_log("用户停止任务")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()

def main():
    print("=" * 50)
    print("  AutoGLM 远程监控版")
    print("=" * 50)
    
    if not DOUBAO_API_KEY:
        print("\n❌ 请先配置 DOUBAO_API_KEY")
        sys.exit(1)
    
    # 获取手机 IP
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "localhost"
    
    print(f"\n📡 模型: {DOUBAO_MODEL}")
    print(f"🔗 Helper: {HELPER_URL}")
    print(f"\n🌐 Web 监控地址:")
    print(f"   http://localhost:{WEB_PORT}")
    print(f"   http://{local_ip}:{WEB_PORT}")
    print(f"\n在电脑浏览器打开上面的地址即可远程监控\n")
    
    server = HTTPServer(('0.0.0.0', WEB_PORT), WebHandler)
    add_log(f"Web 服务器启动在端口 {WEB_PORT}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")

if __name__ == "__main__":
    main()
