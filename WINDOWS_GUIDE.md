# Windows 操作指南

本指南专为 Windows 用户编写，帮助你在 Windows 环境下构建和使用 Open-AutoGLM 项目。

---

## 📋 前提条件

### 必需软件

1. **JDK 17+**
   - 下载: https://adoptium.net/ (推荐 Eclipse Temurin)
   - 或使用 winget: `winget install EclipseAdoptium.Temurin.17.JDK`

2. **Android Studio** (推荐) 或 **Android SDK**
   - 下载: https://developer.android.com/studio

3. **Git** (可选，用于版本控制)
   - 下载: https://git-scm.com/download/win
   - 或使用 winget: `winget install Git.Git`

### 环境变量配置

1. 打开 "系统属性" → "高级" → "环境变量"
2. 添加以下变量:

```
JAVA_HOME = C:\Program Files\Eclipse Adoptium\jdk-17.x.x
ANDROID_HOME = C:\Users\你的用户名\AppData\Local\Android\Sdk
```

3. 在 `Path` 中添加:
```
%JAVA_HOME%\bin
%ANDROID_HOME%\platform-tools
```

---

## 🔨 方式 1: 使用 Android Studio (推荐)

最简单的方式，无需命令行操作。

### 步骤

1. **打开项目**
   - 启动 Android Studio
   - File → Open → 选择 `android-app` 文件夹

2. **等待 Gradle 同步**
   - 首次打开会自动下载依赖
   - 等待右下角进度条完成

3. **构建 APK**
   - 菜单: Build → Build Bundle(s) / APK(s) → Build APK(s)
   - 等待构建完成
   - 点击右下角 "locate" 打开 APK 所在文件夹

4. **APK 位置**
   ```
   android-app\app\build\outputs\apk\debug\app-debug.apk
   ```

---

## 🔨 方式 2: 使用命令行

### 步骤

1. **打开 CMD 或 PowerShell**
   - 按 `Win + R`，输入 `cmd` 或 `powershell`

2. **进入项目目录**
   ```cmd
   cd 你的项目路径\android-app
   ```

3. **构建 APK**
   ```cmd
   gradlew.bat assembleDebug
   ```

4. **等待构建完成**
   - 首次构建约 5-10 分钟
   - 看到 `BUILD SUCCESSFUL` 表示成功

5. **APK 位置**
   ```
   app\build\outputs\apk\debug\app-debug.apk
   ```

### 常用命令

```cmd
:: 清理项目
gradlew.bat clean

:: 构建 Debug APK
gradlew.bat assembleDebug

:: 构建 Release APK
gradlew.bat assembleRelease

:: 清理后重新构建
gradlew.bat clean assembleDebug

:: 查看所有可用任务
gradlew.bat tasks
```

---

## 🔨 方式 3: 使用 GitHub Actions (无需本地环境)

如果不想在本地配置环境，可以使用 GitHub 自动构建。

### 步骤

1. **上传代码到 GitHub**
   - 创建 GitHub 仓库
   - 上传项目文件

2. **等待自动构建**
   - 访问仓库的 Actions 页面
   - 等待构建完成 (约 5-10 分钟)

3. **下载 APK**
   - 点击构建任务
   - 在 Artifacts 部分下载 APK

详细步骤请参考 [GITHUB_BUILD_GUIDE.md](GITHUB_BUILD_GUIDE.md)

---

## 📱 安装 APK 到手机

### 方式 1: 使用 ADB

1. **手机开启 USB 调试**
   - 设置 → 关于手机 → 连续点击"版本号" 7 次
   - 设置 → 开发者选项 → USB 调试 → 开启

2. **连接手机到电脑**

3. **安装 APK**
   ```cmd
   adb install app\build\outputs\apk\debug\app-debug.apk
   ```

### 方式 2: 直接传输

1. 将 APK 文件复制到手机
2. 在手机上点击 APK 文件安装
3. 允许安装未知来源应用

---

## 🐛 常见问题

### 问题 1: 'gradlew' 不是内部或外部命令

**原因**: 没有进入正确的目录

**解决**:
```cmd
cd android-app
gradlew.bat assembleDebug
```

### 问题 2: JAVA_HOME 未设置

**错误信息**: `JAVA_HOME is not set`

**解决**:
1. 确认已安装 JDK
2. 设置环境变量:
   ```cmd
   set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-17.x.x
   ```
3. 或在系统环境变量中永久设置

### 问题 3: SDK 未找到

**错误信息**: `SDK location not found`

**解决**:
1. 在 `android-app` 目录创建 `local.properties` 文件
2. 添加内容:
   ```
   sdk.dir=C:\\Users\\你的用户名\\AppData\\Local\\Android\\Sdk
   ```
   注意: 路径中使用双反斜杠 `\\`

### 问题 4: 构建失败 - 网络问题

**错误信息**: `Could not resolve dependencies`

**解决**:
- 检查网络连接
- 如果在公司网络，可能需要配置代理
- 在 `gradle.properties` 中添加代理设置:
  ```
  systemProp.http.proxyHost=代理地址
  systemProp.http.proxyPort=代理端口
  systemProp.https.proxyHost=代理地址
  systemProp.https.proxyPort=代理端口
  ```

### 问题 5: 内存不足

**错误信息**: `OutOfMemoryError`

**解决**:
在 `gradle.properties` 中增加内存:
```
org.gradle.jvmargs=-Xmx4096m
```

---

## 📁 快速构建脚本

创建 `build.bat` 文件:

```batch
@echo off
echo ========================================
echo   AutoGLM Helper APK 构建脚本
echo ========================================
echo.

cd android-app

echo [1/2] 清理项目...
call gradlew.bat clean

echo [2/2] 构建 APK...
call gradlew.bat assembleDebug

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   构建成功!
    echo   APK 位置: app\build\outputs\apk\debug\app-debug.apk
    echo ========================================
    
    :: 复制到根目录
    copy app\build\outputs\apk\debug\app-debug.apk ..\AutoGLM-Helper.apk
    echo   已复制到: AutoGLM-Helper.apk
) else (
    echo.
    echo ========================================
    echo   构建失败! 请检查错误信息
    echo ========================================
)

pause
```

双击运行即可自动构建。

---

## ✅ 检查清单

构建前确认:

- [ ] 已安装 JDK 17+
- [ ] 已安装 Android Studio 或 Android SDK
- [ ] 已配置 JAVA_HOME 环境变量
- [ ] 已配置 ANDROID_HOME 环境变量
- [ ] 网络连接正常

---

## 📞 需要帮助?

如果遇到问题:
1. 查看上方"常见问题"部分
2. 运行 `gradlew.bat assembleDebug --stacktrace` 查看详细错误
3. 在项目 Issues 中提问

---

## 🤖 视觉大模型配置

本项目支持豆包视觉大模型作为 AI 后端。

### 豆包视觉大模型配置

在 Termux 或本地环境中设置以下环境变量：

```cmd
:: Windows CMD
set DOUBAO_API_KEY=your_api_key_here
set DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3
set DOUBAO_MODEL=doubao-seed-1-6-vision-250815
set DOUBAO_BATCH_ENDPOINT=ep-bi-20251202180029-rfkcl
```

```powershell
# PowerShell
$env:DOUBAO_API_KEY = "your_api_key_here"
$env:DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
$env:DOUBAO_MODEL = "doubao-seed-1-6-vision-250815"
$env:DOUBAO_BATCH_ENDPOINT = "ep-bi-20251202180029-rfkcl"
```

### 永久设置环境变量

1. 打开 "系统属性" → "高级" → "环境变量"
2. 在 "用户变量" 中添加:
   - `DOUBAO_API_KEY` = 你的 API Key
   - `DOUBAO_API_URL` = `https://ark.cn-beijing.volces.com/api/v3`
   - `DOUBAO_MODEL` = `doubao-seed-1-6-vision-250815`
   - `DOUBAO_BATCH_ENDPOINT` = `ep-bi-20251202180029-rfkcl`

### 配置文件方式

创建 `.env` 文件：

```
DOUBAO_API_KEY=your_api_key_here
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seed-1-6-vision-250815
DOUBAO_BATCH_ENDPOINT=ep-bi-20251202180029-rfkcl
```

---

*最后更新: 2024-12-11*
