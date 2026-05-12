# 桌面宠物应用

这是一个透明桌面宠物，会显示提供的角色图片，并带有轻量交互、待机动作和右键菜单。

## 运行

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

也可以调整初始大小：

```bash
python main.py --size 320
```

## 操作

- 左键单击：回应、压扁弹起、显示一句话
- Shift + 左键单击：跳舞
- Ctrl + 左键单击：转圈
- Alt + 左键单击：打盹
- 左键拖动：移动桌宠，松手后会带一点滑行动作
- 鼠标滚轮：缩放角色，并触发伸展/压扁动作
- Ctrl + 鼠标滚轮：转圈或摇一摇
- 左键双击：跳起来转一圈
- 鼠标中键：切换“跟随鼠标”
- 鼠标移入：探头回应
- 空闲时：偶尔自动散步、跳动、跳舞、伸懒腰、打盹或说一句话
- 右键：打开菜单，可说话、跳跃、跳舞、转圈、摇一摇、伸懒腰、打盹、变大/变小、开关自动散步、开关跟随鼠标、回到右下角或退出

## 打包为可执行文件

先安装 PyInstaller：

```bash
pip install pyinstaller
```

Windows：

```bash
pyinstaller --onefile --windowed --name CharacterPet --add-data "pet_character.png;." main.py
```

macOS/Linux：

```bash
pyinstaller --onefile --windowed --name CharacterPet --add-data "pet_character.png:." main.py
```

打包结果在 `dist/` 目录中。
