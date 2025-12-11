#!/usr/bin/env python3
"""
Open-AutoGLM 混合方案 - 独立运行脚本
使用豆包视觉大模型 + AutoGLM Helper APP

无需 ADB，直接通过 HTTP 控制手机
"""

import os
import sys
import base64
import requests
import time
import json
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    print("请安装 Pillow: pip install pillow")
    sys.exit(1)

# ============== 配置 ==============

# 豆包视觉大模型配置
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-seed-1-6-vision-250815")

# AutoGLM Helper 配置
HELPER_URL = os.getenv("AUTOGLM_HELPER_URL", "http://localhost:8080")

# ============== 手机控制器 ==============

class PhoneController:
    """通过 AutoGLM Helper HTTP 接口控制手机"""
    
    def __init__(self, helper_url: str = HELPER_URL):
        self.helper_url = helper_url
        self._check_connection()
    
    def _check_connection(self):
        """检查与 AutoGLM Helper 的连接"""
        try:
            resp = requests.get(f"{self.helper_url}/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('accessibility_enabled'):
                    print(f"✅ 已连接到 AutoGLM Helper")
                    return True
                else:
                    print("⚠️ AutoGLM Helper 运行中，但无障碍服务未开启")
                    print("   请在手机上开启无障碍权限")
                    return False
        except Exception as e:
            print(f"❌ 无法连接到 AutoGLM Helper: {e}")
            print("   请确保:")
            print("   1. AutoGLM Helper APP 已打开")
            print("   2. 无障碍服务已开启")
            return False
        return False
    
    def screenshot(self) -> Image.Image:
        """截取屏幕"""
        try:
            resp = requests.get(f"{self.helper_url}/screenshot", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') and data.get('image'):
                    image_data = base64.b64decode(data['image'])
                    return Image.open(BytesIO(image_data))
        except Exception as e:
            print(f"截图失败: {e}")
        return None
    
    def tap(self, x: int, y: int) -> bool:
        """点击指定坐标"""
        try:
            resp = requests.post(
                f"{self.helper_url}/tap",
                json={'x': x, 'y': y},
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json().get('success', False)
        except Exception as e:
            print(f"点击失败: {e}")
        return False
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 500) -> bool:
        """滑动"""
        try:
            resp = requests.post(
                f"{self.helper_url}/swipe",
                json={'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'duration': duration},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json().get('success', False)
        except Exception as e:
            print(f"滑动失败: {e}")
        return False
    
    def input_text(self, text: str) -> bool:
        """输入文字"""
        try:
            resp = requests.post(
                f"{self.helper_url}/input",
                json={'text': text},
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json().get('success', False)
        except Exception as e:
            print(f"输入失败: {e}")
        return False
    
    def back(self) -> bool:
        """返回键"""
        try:
            resp = requests.post(f"{self.helper_url}/back", timeout=5)
            if resp.status_code == 200:
                return resp.json().get('success', False)
        except Exception as e:
            print(f"返回失败: {e}")
        return False
    
    def home(self) -> bool:
        """主页键"""
        try:
            resp = requests.post(f"{self.helper_url}/home", timeout=5)
            if resp.status_code == 200:
                return resp.json().get('success', False)
        except Exception as e:
            print(f"主页失败: {e}")
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
            print("   请设置环境变量或在 ~/.autoglm/config.sh 中配置")
            sys.exit(1)
    
    def analyze_screen(self, image: Image.Image, task: str) -> dict:
        """
        分析屏幕截图，返回下一步操作
        
        Returns:
            {
                'action': 'tap' | 'swipe' | 'input' | 'back' | 'home' | 'done' | 'failed',
                'params': {...},  # 操作参数
                'thought': '...'  # 思考过程
            }
        """
        # 获取图片尺寸
        width, height = image.size
        
        # 将图片转为 base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # 构建提示词
        prompt = f"""你是一个手机自动化助手，负责控制 Android 手机完成用户任务。

【用户任务】{task}

【屏幕信息】
- 屏幕分辨率：宽 {width} 像素，高 {height} 像素
- 坐标系：左上角为 (0,0)，右下角为 ({width},{height})

【重要规则】
1. 仔细观察屏幕上的所有元素（图标、按钮、文字、输入框）
2. 点击坐标必须精确到目标元素的中心位置
3. 如果要点击某个 APP 图标，坐标应该在图标的正中央
4. 如果要点击按钮或文字，坐标应该在该元素的中心
5. 如果当前屏幕已经显示任务目标（如已打开淘宝并显示搜索结果），返回 done

【操作类型】
- tap: 点击，需要精确的 x,y 坐标
- swipe: 滑动，从 (x1,y1) 滑到 (x2,y2)
- input: 输入文字（需要先点击输入框激活）
- back: 返回上一页
- home: 回到桌面
- done: 任务完成
- failed: 无法完成

【返回格式】只返回 JSON，格式如下：
{{"action": "操作类型", "params": {{参数}}, "thought": "思考过程"}}

【示例】
- 点击屏幕中央的淘宝图标：{{"action": "tap", "params": {{"x": {width//2}, "y": {height//2}}}, "thought": "点击淘宝图标"}}
- 在搜索框输入：{{"action": "input", "params": {{"text": "蓝牙耳机"}}, "thought": "输入搜索词"}}
- 向上滑动：{{"action": "swipe", "params": {{"x1": {width//2}, "y1": {int(height*0.7)}, "x2": {width//2}, "y2": {int(height*0.3)}}}, "thought": "向上滑动"}}
- 任务完成：{{"action": "done", "params": {{}}, "thought": "已完成搜索，显示结果"}}

现在请分析屏幕并返回下一步操作（只返回JSON）："""

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
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                        }
                    ]
                }
            ],
            "max_tokens": 500
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
                content = result['choices'][0]['message']['content']
                
                # 解析 JSON
                # 尝试提取 JSON 部分
                content = content.strip()
                if content.startswith("```"):
                    # 移除 markdown 代码块
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1])
                
                return json.loads(content)
            else:
                print(f"API 错误: {resp.status_code} - {resp.text}")
                return {"action": "failed", "params": {}, "thought": "API 调用失败"}
                
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            print(f"原始响应: {content}")
            return {"action": "failed", "params": {}, "thought": "响应解析失败"}
        except Exception as e:
            print(f"模型调用失败: {e}")
            return {"action": "failed", "params": {}, "thought": str(e)}

# ============== 主程序 ==============

class AutoGLMAgent:
    """AutoGLM 自动化代理"""
    
    def __init__(self):
        self.controller = PhoneController()
        self.model = DoubaoVisionModel()
        self.max_steps = 20
    
    def run(self, task: str):
        """执行任务"""
        print(f"\n📋 任务: {task}")
        print("=" * 50)
        
        for step in range(1, self.max_steps + 1):
            print(f"\n🔄 步骤 {step}/{self.max_steps}")
            
            # 1. 截图
            print("  📸 截取屏幕...")
            screenshot = self.controller.screenshot()
            if screenshot is None:
                print("  ❌ 截图失败")
                continue
            
            # 2. 分析
            print("  🤔 分析屏幕...")
            result = self.model.analyze_screen(screenshot, task)
            
            action = result.get('action', 'failed')
            params = result.get('params', {})
            thought = result.get('thought', '')
            
            print(f"  💭 思考: {thought}")
            print(f"  🎯 操作: {action} {params}")
            
            # 3. 执行
            if action == 'done':
                print("\n✅ 任务完成!")
                return True
            elif action == 'failed':
                print("\n❌ 任务失败")
                return False
            elif action == 'tap':
                x, y = params.get('x', 0), params.get('y', 0)
                self.controller.tap(x, y)
            elif action == 'swipe':
                x1, y1 = params.get('x1', 0), params.get('y1', 0)
                x2, y2 = params.get('x2', 0), params.get('y2', 0)
                self.controller.swipe(x1, y1, x2, y2)
            elif action == 'input':
                text = params.get('text', '')
                self.controller.input_text(text)
            elif action == 'back':
                self.controller.back()
            elif action == 'home':
                self.controller.home()
            
            # 等待操作生效
            time.sleep(1.5)
        
        print("\n⚠️ 达到最大步数限制")
        return False


def main():
    print("=" * 50)
    print("  Open-AutoGLM 混合方案")
    print("  豆包视觉大模型 + AutoGLM Helper")
    print("=" * 50)
    
    # 检查配置
    if not DOUBAO_API_KEY:
        print("\n❌ 请先配置豆包 API Key:")
        print("   export DOUBAO_API_KEY='your_key'")
        print("   或运行 source ~/.autoglm/config.sh")
        sys.exit(1)
    
    print(f"\n📡 模型: {DOUBAO_MODEL}")
    print(f"🔗 Helper: {HELPER_URL}")
    
    agent = AutoGLMAgent()
    
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
