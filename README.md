# ✂️ Jianying Beat Auto-Cut

<p align="center">
  <a href="#english">English</a> | <a href="#中文">中文</a>
</p>

---

<div id="english"></div>

## English

An **AI-assisted automated video editing tool** that analyzes audio beat points, cuts video materials precisely by beats, and generates **Jianying (CapCut)** draft files.

Perfect for batch-producing short-form videos where you need video cuts aligned to music beats.

### ✨ Features

| Feature | Description |
|---|---|
| **Batch Upload** | Upload multiple video materials and audio tracks at once |
| **Beat Detection** | Analyze audio beats using `librosa` library |
| **Per-Beat Cut** | Automatically cut video segments aligned to each beat point |
| **Draft Generation** | Generate Jianying (CapCut) compatible draft files |
| **Dual Mode** | Desktop app (PyQt) + Web app (Flask) |
| **Multi-Audio** | Each audio track generates an independent editing draft |
| **Report Export** | Processing reports saved with detailed stats |

### 🏗 Architecture

```
Jianying Beat Auto-Cut
├── Audio Analysis (librosa)
│   ├── Load audio file
│   ├── Extract beat frames
│   └── Calculate beat timestamps
├── Video Processing
│   ├── Load video materials
│   ├── Cut by beat timestamps
│   └── Sequence arrangement
├── Draft Generation (pyJianYingDraft)
│   ├── Create Jianying draft JSON
│   ├── Map video segments to timeline
│   └── Export to Jianying drafts folder
└── App Layer
    ├── Desktop App (PyQt5)
    └── Web App (Flask)
```

### 🚀 Quick Start

#### Desktop App (Recommended)

```powershell
# Run directly
python jianying_autocut_desktop.py

# Or double-click the launcher
start_desktop_app.bat
```

#### Web App

```powershell
python jianying_autocut_webapp.py
# Then open http://127.0.0.1:5000
```

#### CLI / Core Script

```powershell
python jianying_beat_autocut.py --video_dir ./videos --audio_dir ./audio --output ./drafts
```

#### Build Standalone EXE

```powershell
.\build_desktop_exe.bat
# Output: .\dist\JianyingAutoCutApp\JianyingAutoCutApp.exe
```

### 📦 Project Structure

```
jianying-beat-autocut/
├── jianying_beat_autocut.py       # Core beat detection & cutting engine
├── jianying_autocut_desktop.py    # Desktop GUI application
├── jianying_autocut_webapp.py     # Flask web application
├── test_jianying_beat_autocut.py  # Unit tests for core logic
├── test_batch_helpers.py          # Batch processing test utilities
├── test_asset_templates.py        # Asset template tests
├── last_run_report.json           # Last execution report
├── build_desktop_exe.bat          # PyInstaller build script
└── README.md
```

### 🛠 Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Core language |
| librosa | Audio signal processing & beat detection |
| numpy | Numerical computing |
| pyJianYingDraft | Jianying draft file generation |
| Flask | Web app backend |
| PyQt5 / PySide | Desktop GUI framework |
| PyInstaller | Standalone EXE packaging |

### 📋 Requirements

```powershell
pip install librosa numpy flask pyqt5
# pyJianYingDraft needs to be installed from source or corresponding channel
```

### 🔮 Roadmap

- [ ] Support more video editing software (Premiere, DaVinci)
- [ ] AI-powered beat style classification (drops, build-ups)
- [ ] Transition effect auto-generation
- [ ] Cloud processing for large batches

---

<div id="中文"></div>

## 中文

一款 **AI 辅助自动化视频剪辑工具**，分析音频节拍点，按节拍精准切分视频素材，并生成 **剪映（CapCut）** 可导入的草稿文件。

适用于需要批量制作音乐节拍对齐短视频的场景。

### ✨ 功能特性

| 功能 | 描述 |
|---|---|
| **批量上传** | 同时上传多条视频素材和多条音轨 |
| **节拍检测** | 使用 `librosa` 库分析音频节拍 |
| **按拍切分** | 根据每个节拍点自动切分视频片段 |
| **草稿生成** | 生成剪映（CapCut）兼容的草稿文件 |
| **双端支持** | 桌面应用（PyQt）+ Web 应用（Flask） |
| **多音轨处理** | 每条音轨生成独立的剪辑草稿 |
| **报告导出** | 保存处理报告，包含详细统计信息 |

### 🏗 架构

```
剪映节拍自动切分工具
├── 音频分析 (librosa)
│   ├── 加载音频文件
│   ├── 提取节拍帧
│   └── 计算节拍时间戳
├── 视频处理
│   ├── 加载视频素材
│   ├── 按节拍时间戳切分
│   └── 排列序列
├── 草稿生成 (pyJianYingDraft)
│   ├── 创建剪映草稿 JSON
│   ├── 将视频片段映射到时间轴
│   └── 导出到剪映草稿文件夹
└── 应用层
    ├── 桌面应用 (PyQt5)
    └── Web 应用 (Flask)
```

### 🚀 快速开始

#### 桌面应用（推荐）

```powershell
# 直接运行
python jianying_autocut_desktop.py

# 或双击启动脚本
start_desktop_app.bat
```

#### Web 应用

```powershell
python jianying_autocut_webapp.py
# 然后打开 http://127.0.0.1:5000
```

#### CLI / 核心脚本

```powershell
python jianying_beat_autocut.py --video_dir ./videos --audio_dir ./audio --output ./drafts
```

#### 打包为独立 EXE

```powershell
.\build_desktop_exe.bat
# 输出路径: .\dist\JianyingAutoCutApp\JianyingAutoCutApp.exe
```

### 📦 项目结构

```
jianying-beat-autocut/
├── jianying_beat_autocut.py       # 核心节拍检测与切分引擎
├── jianying_autocut_desktop.py    # 桌面 GUI 应用
├── jianying_autocut_webapp.py     # Flask Web 应用
├── test_jianying_beat_autocut.py  # 核心逻辑单元测试
├── test_batch_helpers.py          # 批量处理测试工具
├── test_asset_templates.py        # 素材模板测试
├── last_run_report.json           # 上次执行报告
├── build_desktop_exe.bat          # PyInstaller 打包脚本
└── README.md
```

### 🛠 技术栈

| 技术 | 用途 |
|---|---|
| Python 3.10+ | 核心语言 |
| librosa | 音频信号处理与节拍检测 |
| numpy | 数值计算 |
| pyJianYingDraft | 剪映草稿文件生成 |
| Flask | Web 应用后端 |
| PyQt5 / PySide | 桌面 GUI 框架 |
| PyInstaller | 独立 EXE 打包 |

### 📋 环境要求

```powershell
pip install librosa numpy flask pyqt5
# pyJianYingDraft 需要从源码或对应渠道安装
```

### 🔮 未来规划

- [ ] 支持更多剪辑软件（Premiere、达芬奇）
- [ ] AI 节拍风格分类（Drop、Build-up 等）
- [ ] 转场特效自动生成
- [ ] 大批量云端处理

---

## License

MIT
