# 粉毛桌面宠物

一个使用 PySide6 制作的 Windows 桌面宠物。窗口透明、可拖拽、可置顶，支持随机散步、气泡台词和互动动作。

## 直接使用

下载 Windows 打包版后，解压整个 `PinkDesktopPet` 文件夹，双击 `PinkDesktopPet.exe` 运行。

注意：不要只单独复制 exe，旁边的 `_internal` 文件夹也需要保留。

## 从源码运行

### Windows

双击 `run_windows.bat`，脚本会创建虚拟环境并安装依赖。

也可以在终端中运行：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 操作

- 左键拖动：移动桌宠
- 左键点击：触发随机互动
- 左键双击：睡觉 / 叫醒
- 右键菜单：摸摸她、打招呼、跳跃、转圈、动作、大小、置顶、退出
- 托盘图标：显示 / 叫醒、退出

## 打包 Windows 版本

```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name PinkDesktopPet --add-data "assets;assets" main.py
```

构建结果在 `dist/PinkDesktopPet/`。
