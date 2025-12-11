#!/usr/bin/env python3
"""
Open-AutoGLM 混合方案 - 独立运行脚本 v1.1
使用豆包视觉大模型 + AutoGLM Helper APP

优化内容:
- 更精准的坐标定位提示词
- 添加重试机制
- 更好的错误处理
- 任务完成检测优化
"""

import os
import sys
import base64
import requests
import time
import json
import re
from io import BytesIO

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

# ============== 手机控制器 ==============
class PhoneController:
    """通过 AutoGLM Helper HTTP 接口控制手机"""
    
    def __init__(self, helper_url: str = HELPER_URL):
        self.helper_url = helper_url
        self.screen_width = 1080
        self.screen_height = 2400
    
    def check_connection(self) -> bool:
        """检查连接状态"""
        try:
            resp = requests.get(f"{self.helper_url}/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('accessibility_enabled'):
                    print("✅ 已连接到 AutoGLM Helper")
                    return True
                else:
                    print("⚠️ AutoGLM Helper 运行中，但无障碍服务未开启")
                    print("   请在手机设置中开启无障碍权限")
                    return False
        except requests.exceptions.ConnectionError:
            print("❌ 无法连接到 AutoGLM Helper")
            print("   请确保 AutoGLM Helper APP 已打开")
        except Exception as e:
            print(f"❌ 连接错误: {e}")
        return False
    
    def screenshot(self) -> Image.Image:
        """截取屏幕，带重试"""
        for attempt in range(3):
            try:
                resp = requests.get(f"{self.helper_url}/screenshot", timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('success') and data.get('image'):
                        image_data = base64.b64decode(data['image'])
                        img = Image.open(BytesIO(image_data))
                        self.screen_width, self.screen_height = img.size
                        return img
            except Exception as e:
                if attempt < 2:
                    print(f"  截图失败，重试 ({attempt+1}/3)...")
                    time.sleep(1)
        return None
    
    def tap(self, x: int, y: int) -> bool:
        """点击指定坐标"""
        # 确保坐标在屏幕范围内
        x = max(0, min(x, self.screen_width))
        y = max(0, min(y, self.screen_height))
        try:
            resp = requests.post(
                f"{self.helper_url}/tap",
                json={'x': x, 'y': y},
                timeout=5
            )
            return resp.status_code == 200 and resp.json().get('success', False)
        except Exception as e:
            print(f"  点击失败: {e}")
        return False
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 500) -> bool:
        """滑动"""
        try:
            resp = requests.post(
                f"{self.helper_url}/swipe",
                json={'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'duration': duration},
                timeout=10
            )
            return resp.status_code == 200 and resp.json().get('success', False)
        except Exception as e:
            print(f"  滑动失败: {e}")
        return False
    
    def input_text(self, text: str) -> bool:
        """输入文字"""
        try:
            resp = requests.post(
                f"{self.helper_url}/input",
                json={'text': text},
                timeout=5
            )
            return resp.status_code == 200 and resp.json().get('success', False)
        except Exception as e:
            print(f"  输入失败: {e}")
        return False
    
    def back(self) -> bool:
        """返回键"""
        try:
            resp = requests.post(f"{self.helper_url}/back", timeout=5)
            return resp.status_code == 200 and resp.json().get('success', False)
        except:
            return False
    
    def home(self) -> bool:
        """主页键"""
        try:
            resp = requests.post(f"{self.helper_url}/home", timeout=5)
            return resp.status_code == 200 and resp.json().get('success', False)
        except:
            return False

# ============== 视觉模型 ==============
class DoubaoVisionModel:
    """豆包视觉大模型"""
    
    def __init__(self):
        self.api_key = DOUBAO_API_KEY
        self.api_url = DOUBAO_API_URL
        self.model = DOUBAO_MODEL
        
        if not self.api_key:
            print("❌ 未配置 DOUBAO_API_KEY")
            sys.exit(1)
    
    def analyze_screen(self, image: Image.Image, task: str, history: list = None) -> dict:
        """分析屏幕截图，返回下一步操作"""
        width, height = image.size
        
        # 将图片转为 base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # 构建历史记录摘要
        history_text = ""
        if history and len(history) > 0:
            recent = history[-5:]  # 最近5步
            history_text = "\n【已执行的操作】\n" + "\n".join([
                f"- {h['thought']}: {h['action']}" for h in recent
            ])
        
        prompt = f"""你是一个专业的手机自动化助手，负责精确控制 Android 手机完成用户任务。

【用户任务】{task}

【屏幕尺寸】{width} x {height} 像素
{history_text}

【坐标定位规则 - 非常重要】
1. 屏幕左上角是 (0, 0)，右下角是 ({width}, {height})
2. 屏幕分为9个区域便于定位：
   - 左上: (0~{width//3}, 0~{height//3})
   - 中上: ({width//3}~{width*2//3}, 0~{height//3})
   - 右上: ({width*2//3}~{width}, 0~{height//3})
   - 左中: (0~{width//3}, {height//3}~{height*2//3})
   - 正中: ({width//3}~{width*2//3}, {height//3}~{height*2//3})
   - 右中: ({width*2//3}~{width}, {height//3}~{height*2//3})
   - 左下: (0~{width//3}, {height*2//3}~{height})
   - 中下: ({width//3}~{width*2//3}, {height*2//3}~{height})
   - 右下: ({width*2//3}~{width}, {height*2//3}~{height})
3. 点击时坐标必须在目标元素的正中心
4. 如果是桌面图标，通常排列整齐，每行4-5个图标

【操作类型】
- tap: 点击 {{"x": 数字, "y": 数字}}
- swipe: 滑动 {{"x1": 起点x, "y1": 起点y, "x2": 终点x, "y2": 终点y}}
- input: 输入文字 {{"text": "文字"}} (需要先点击输入框)
- back: 返回上一页 {{}}
- home: 回到桌面 {{}}
- done: 任务完成 {{}}
- wait: 等待页面加载 {{}}

【判断任务完成的标准】
- 如果任务是"打开XX搜索YY"，当搜索结果页面显示时即为完成
- 如果任务是"打开XX"，当XX应用主界面显示时即为完成
- 不要重复执行已完成的操作

【返回格式】只返回一个JSON对象：
{{"action": "操作类型", "params": {{参数}}, "thought": "简短说明当前屏幕状态和操作原因"}}

现在请仔细观察屏幕截图，返回下一步操作："""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]
                }
            ],
            "max_tokens": 500,
            "temperature": 0.1  # 降低随机性，提高一致性
        }
        
        try:
            resp = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=60
            )
            
            if resp.status_code == 200:
                result = resp.json()
                content = result['choices'][0]['message']['content'].strip()
                return self._parse_response(content)
            else:
                print(f"  API 错误: {resp.status_code}")
                return {"action": "wait", "params": {}, "thought": "API调用失败，等待重试"}
                
        except Exception as e:
            print(f"  模型调用失败: {e}")
            return {"action": "wait", "params": {}, "thought": str(e)}
    
    def _parse_response(self, content: str) -> dict:
        """解析模型响应"""
        try:
            # 移除 markdown 代码块
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            
            # 尝试提取 JSON
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"  JSON 解析失败: {content[:100]}...")
            return {"action": "wait", "params": {}, "thought": "响应解析失败"}

# ============== 主程序 ==============
class AutoGLMAgent:
    """AutoGLM 自动化代理"""
    
    def __init__(self):
        self.controller = PhoneController()
        self.model = DoubaoVisionModel()
        self.max_steps = 25
        self.history = []
    
    def run(self, task: str) -> bool:
        """执行任务"""
        print(f"\n📋 任务: {task}")
        print("=" * 50)
        
        self.history = []
        consecutive_failures = 0
        last_action = None
        
        for step in range(1, self.max_steps + 1):
            print(f"\n🔄 步骤 {step}/{self.max_steps}")
            
            # 1. 截图
            print("  📸 截取屏幕...")
            screenshot = self.controller.screenshot()
            if screenshot is None:
                print("  ❌ 截图失败")
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print("\n❌ 连续截图失败，请检查 AutoGLM Helper")
                    return False
                time.sleep(2)
                continue
            
            consecutive_failures = 0
            
            # 2. 分析
            print("  🤔 分析屏幕...")
            result = self.model.analyze_screen(screenshot, task, self.history)
            
            action = result.get('action', 'wait')
            params = result.get('params', {})
            thought = result.get('thought', '')
            
            print(f"  💭 {thought}")
            print(f"  🎯 {action}: {params}")
            
            # 检测重复操作
            current_action = f"{action}:{params}"
            if current_action == last_action and action not in ['done', 'wait']:
                print("  ⚠️ 检测到重复操作，尝试其他方式...")
                action = 'wait'
            last_action = current_action
            
            # 记录历史
            self.history.append({
                'step': step,
                'action': f"{action} {params}",
                'thought': thought
            })
            
            # 3. 执行
            success = self._execute_action(action, params)
            
            if action == 'done':
                print("\n✅ 任务完成!")
                return True
            
            if not success and action not in ['wait', 'done']:
                print("  ⚠️ 操作执行失败")
            
            # 等待操作生效
            wait_time = 2.0 if action in ['tap', 'input'] else 1.5
            time.sleep(wait_time)
        
        print("\n⚠️ 达到最大步数限制")
        return False
    
    def _execute_action(self, action: str, params: dict) -> bool:
        """执行操作"""
        if action == 'done':
            return True
        elif action == 'wait':
            time.sleep(1)
            return True
        elif action == 'tap':
            x, y = int(params.get('x', 0)), int(params.get('y', 0))
            return self.controller.tap(x, y)
        elif action == 'swipe':
            x1, y1 = int(params.get('x1', 0)), int(params.get('y1', 0))
            x2, y2 = int(params.get('x2', 0)), int(params.get('y2', 0))
            return self.controller.swipe(x1, y1, x2, y2)
        elif action == 'input':
            text = params.get('text', '')
            return self.controller.input_text(text)
        elif action == 'back':
            return self.controller.back()
        elif action == 'home':
            return self.controller.home()
        return False


def main():
    print("=" * 50)
    print("  Open-AutoGLM 混合方案 v1.1")
    print("  豆包视觉大模型 + AutoGLM Helper")
    print("=" * 50)
    
    if not DOUBAO_API_KEY:
        print("\n❌ 请先配置豆包 API Key:")
        print("   export DOUBAO_API_KEY='your_key'")
        sys.exit(1)
    
    print(f"\n📡 模型: {DOUBAO_MODEL}")
    print(f"🔗 Helper: {HELPER_URL}")
    
    agent = AutoGLMAgent()
    
    # 检查连接
    if not agent.controller.check_connection():
        print("\n请先确保 AutoGLM Helper 正常运行")
        sys.exit(1)
    
    print("\n输入任务开始执行，输入 'quit' 退出\n")
    
    while True:
        try:
            task = input("请输入任务: ").strip()
            
            if task.lower() in ('quit', 'exit', 'q'):
                print("再见!")
                break
            
            if not task:
                continue
            
            agent.run(task)
            print()
            
        except KeyboardInterrupt:
            print("\n\n已中断，再见!")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    main()
