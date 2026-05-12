"""Interactive transparent desktop pet using the supplied character image."""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QAction, QCursor, QPixmap, QTransform
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QToolTip


def resource_path(name: str) -> str:
    """Resolve bundled assets in normal Python runs and PyInstaller builds."""
    base_dir = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base_dir) / name)


class DesktopPet(QLabel):
    def __init__(self, image_path: str, height: int = 260, fps: int = 30) -> None:
        super().__init__()
        self.image_path = image_path
        self.pet_height = height
        self.base_pixmap = QPixmap(image_path)
        if self.base_pixmap.isNull():
            raise FileNotFoundError(f"Cannot load pet image: {image_path}")

        self.messages = [
            "我在这儿。",
            "摸摸头？",
            "今天也要开心。",
            "我会乖乖待着。",
            "刚刚是不是叫我？",
            "桌面巡逻中。",
            "要休息一下吗？",
            "收到一个摸摸。",
            "我刚学会新动作。",
            "看我转一下。",
        ]
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.press_global_pos = QPoint(0, 0)
        self.moved_during_press = False
        self.last_drag_pos = QPoint(0, 0)
        self.base_pos = QPoint(80, 80)
        self.frame = 0
        self.jump_frame = 0
        self.jump_total_frames = 0
        self.action_name: str | None = None
        self.action_frame = 0
        self.action_total = 0
        self.slide_velocity = QPoint(0, 0)
        self.wander_enabled = True
        self.follow_mouse = False
        self.wander_target: QPoint | None = None
        self.idle_cooldown = random.randint(90, 180)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self.render_pet()
        self.place_near_bottom_right()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(max(1, int(1000 / fps)))

    def render_pet(self, height_delta: int = 0, rotation: float = 0.0) -> None:
        scaled = self.base_pixmap.scaledToHeight(
            max(80, self.pet_height + height_delta),
            Qt.TransformationMode.SmoothTransformation,
        )
        if rotation:
            scaled = scaled.transformed(
                QTransform().rotate(rotation),
                Qt.TransformationMode.SmoothTransformation,
            )
        self.setPixmap(scaled)
        self.setFixedSize(scaled.size())

    def place_near_bottom_right(self) -> None:
        area = self.screen_area()
        if area is None:
            self.base_pos = QPoint(80, 80)
            self.move(self.base_pos)
            return
        x = max(area.left(), area.right() - self.width() - 40)
        y = max(area.top(), area.bottom() - self.height() - 40)
        self.base_pos = QPoint(x, y)
        self.wander_target = None
        self.slide_velocity = QPoint(0, 0)
        self.move(self.base_pos)

    def animate(self) -> None:
        if self.dragging:
            return

        self.frame += 1
        self.idle_cooldown -= 1

        if self.follow_mouse:
            self.step_toward_cursor()
        elif self.slide_velocity.manhattanLength() > 1:
            self.step_slide()
        elif self.wander_enabled:
            self.step_wander()

        if self.idle_cooldown <= 0:
            self.do_idle_action()

        action_offset, height_delta, rotation = self.advance_action()
        bob = int(math.sin(self.frame / 14.0) * 4)
        jump = self.advance_jump()

        self.render_pet(height_delta=height_delta, rotation=rotation)
        target_pos = self.clamp_to_screen(
            QPoint(self.base_pos.x() + action_offset.x(), self.base_pos.y() + action_offset.y() + bob + jump)
        )
        self.move(target_pos)

    def advance_jump(self) -> int:
        if not self.jump_total_frames:
            return 0
        progress = self.jump_frame / self.jump_total_frames
        jump = -int(math.sin(progress * math.pi) * 58)
        self.jump_frame += 1
        if self.jump_frame > self.jump_total_frames:
            self.jump_frame = 0
            self.jump_total_frames = 0
        return jump

    def advance_action(self) -> tuple[QPoint, int, float]:
        if self.action_name is None:
            return QPoint(0, 0), 0, 0.0

        self.action_frame += 1
        progress = min(1.0, self.action_frame / max(1, self.action_total))
        offset = QPoint(0, 0)
        height_delta = 0
        rotation = 0.0

        if self.action_name == "shake":
            offset = QPoint(int(math.sin(self.action_frame * 1.7) * 14), 0)
            rotation = math.sin(self.action_frame * 1.7) * 5
        elif self.action_name == "dance":
            offset = QPoint(int(math.sin(self.action_frame / 3.0) * 18), -abs(int(math.sin(self.action_frame / 4.0) * 18)))
            rotation = math.sin(self.action_frame / 3.0) * 8
            height_delta = int(math.sin(self.action_frame / 2.0) * 8)
        elif self.action_name == "spin":
            rotation = progress * 360
            height_delta = int(math.sin(progress * math.pi) * 16)
        elif self.action_name == "stretch":
            height_delta = int(math.sin(progress * math.pi) * 45)
            offset = QPoint(0, -height_delta // 2)
        elif self.action_name == "squish":
            height_delta = -int(math.sin(progress * math.pi) * 35)
            offset = QPoint(0, int(math.sin(progress * math.pi) * 12))
        elif self.action_name == "nap":
            rotation = -10
            offset = QPoint(0, 8)
            if self.action_frame % 24 == 1:
                self.say("Zzz...")
        elif self.action_name == "peek":
            offset = QPoint(0, int(math.sin(progress * math.pi * 2) * 18))
        elif self.action_name == "dash":
            offset = QPoint(int(math.sin(progress * math.pi * 6) * 10), -abs(int(math.sin(progress * math.pi) * 22)))

        if self.action_frame >= self.action_total:
            self.action_name = None
            self.action_frame = 0
            self.action_total = 0
            self.render_pet()

        return offset, height_delta, rotation

    def do_idle_action(self) -> None:
        self.idle_cooldown = random.randint(150, 300)
        choice = random.choice(["say", "jump", "dance", "stretch", "nap", "wander"])
        if choice == "say":
            self.say(random.choice(self.messages))
        elif choice == "jump":
            self.start_jump(total_frames=random.randint(18, 28))
        elif choice == "wander" and self.wander_enabled:
            self.pick_wander_target()
        else:
            self.start_action(choice)

    def start_jump(self, total_frames: int = 22) -> None:
        self.jump_frame = 0
        self.jump_total_frames = total_frames

    def start_action(self, name: str, total_frames: int | None = None) -> None:
        default_frames = {
            "shake": 22,
            "dance": 72,
            "spin": 34,
            "stretch": 38,
            "squish": 20,
            "nap": 96,
            "peek": 26,
            "dash": 34,
        }
        self.action_name = name
        self.action_frame = 0
        self.action_total = total_frames or default_frames.get(name, 30)

    def react_to_click(self, modifiers: Qt.KeyboardModifier) -> None:
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.start_action("dance")
            self.say("开跳。")
        elif modifiers & Qt.KeyboardModifier.ControlModifier:
            self.start_action("spin")
            self.say("转圈。")
        elif modifiers & Qt.KeyboardModifier.AltModifier:
            self.start_action("nap")
            self.say("小睡一下。")
        else:
            self.start_action("squish")
            self.start_jump(total_frames=18)
            self.say(random.choice(self.messages))

    def say(self, text: str) -> None:
        QToolTip.showText(self.mapToGlobal(QPoint(self.width() // 2, -8)), text, self)

    def set_pet_height(self, height: int) -> None:
        old_center = self.geometry().center()
        self.pet_height = max(120, min(640, height))
        self.render_pet()
        new_top_left = old_center - QPoint(self.width() // 2, self.height() // 2)
        self.base_pos = self.clamp_to_screen(new_top_left)
        self.move(self.base_pos)

    def screen_area(self):
        screen = QApplication.primaryScreen()
        return None if screen is None else screen.availableGeometry()

    def clamp_to_screen(self, point: QPoint) -> QPoint:
        area = self.screen_area()
        if area is None:
            return point
        x = max(area.left(), min(point.x(), area.right() - self.width()))
        y = max(area.top(), min(point.y(), area.bottom() - self.height()))
        return QPoint(x, y)

    def pick_wander_target(self) -> None:
        area = self.screen_area()
        if area is None:
            return
        max_x = max(area.left(), area.right() - self.width())
        min_y = max(area.top(), area.bottom() - self.height() - 100)
        max_y = max(area.top(), area.bottom() - self.height())
        self.wander_target = QPoint(
            random.randint(area.left(), max_x),
            random.randint(min_y, max_y),
        )

    def step_wander(self) -> None:
        if self.wander_target is None or (self.base_pos - self.wander_target).manhattanLength() < 8:
            if random.random() < 0.01:
                self.pick_wander_target()
            return
        self.base_pos = self.step_toward(self.base_pos, self.wander_target, speed=2)

    def step_toward_cursor(self) -> None:
        cursor = QCursor.pos()
        target = QPoint(cursor.x() - self.width() // 2, cursor.y() - self.height() - 22)
        self.base_pos = self.step_toward(self.base_pos, self.clamp_to_screen(target), speed=5)

    def step_slide(self) -> None:
        next_pos = self.clamp_to_screen(self.base_pos + self.slide_velocity)
        if next_pos == self.base_pos:
            self.slide_velocity = QPoint(0, 0)
            self.start_action("shake", total_frames=14)
            return
        self.base_pos = next_pos
        self.slide_velocity = QPoint(int(self.slide_velocity.x() * 0.88), int(self.slide_velocity.y() * 0.88))

    @staticmethod
    def step_toward(start: QPoint, target: QPoint, speed: int) -> QPoint:
        dx = target.x() - start.x()
        dy = target.y() - start.y()
        distance = max(1.0, math.hypot(dx, dy))
        if distance <= speed:
            return target
        return QPoint(
            start.x() + int(dx / distance * speed),
            start.y() + int(dy / distance * speed),
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.moved_during_press = False
            self.press_global_pos = event.globalPosition().toPoint()
            self.last_drag_pos = self.base_pos
            self.slide_velocity = QPoint(0, 0)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.start_action("shake", total_frames=10)
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.toggle_follow_mouse(not self.follow_mouse)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_offset
            self.moved_during_press = (
                self.moved_during_press
                or (event.globalPosition().toPoint() - self.press_global_pos).manhattanLength() > 6
            )
            self.last_drag_pos = self.base_pos
            self.base_pos = self.clamp_to_screen(new_pos)
            self.move(self.base_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.base_pos = self.clamp_to_screen(self.pos())
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self.moved_during_press:
                delta = self.base_pos - self.last_drag_pos
                self.slide_velocity = QPoint(
                    max(-18, min(18, delta.x())),
                    max(-18, min(18, delta.y())),
                )
                self.start_action("dash", total_frames=20)
            else:
                self.react_to_click(event.modifiers())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_jump()
            self.start_action("spin")
            self.say("跳起来转一圈。")
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API name
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.start_action("spin" if delta > 0 else "shake")
        else:
            self.set_pet_height(self.pet_height + (18 if delta > 0 else -18))
            self.start_action("stretch" if delta > 0 else "squish", total_frames=18)
        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setWindowOpacity(0.96)
        self.start_action("peek", total_frames=20)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setWindowOpacity(1.0)
        super().leaveEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt API name
        menu = QMenu(self)
        say_action = QAction("说一句", self)
        jump_action = QAction("跳一下", self)
        dance_action = QAction("跳舞", self)
        spin_action = QAction("转圈", self)
        shake_action = QAction("摇一摇", self)
        stretch_action = QAction("伸懒腰", self)
        nap_action = QAction("打个盹", self)
        bigger_action = QAction("变大一点", self)
        smaller_action = QAction("变小一点", self)
        wander_action = QAction("自动散步", self)
        follow_action = QAction("跟随鼠标", self)
        reset_action = QAction("回到右下角", self)
        close_action = QAction("退出", self)

        wander_action.setCheckable(True)
        wander_action.setChecked(self.wander_enabled)
        follow_action.setCheckable(True)
        follow_action.setChecked(self.follow_mouse)

        say_action.triggered.connect(lambda _checked=False: self.say(random.choice(self.messages)))
        jump_action.triggered.connect(lambda _checked=False: self.start_jump())
        dance_action.triggered.connect(lambda _checked=False: self.start_action("dance"))
        spin_action.triggered.connect(lambda _checked=False: self.start_action("spin"))
        shake_action.triggered.connect(lambda _checked=False: self.start_action("shake"))
        stretch_action.triggered.connect(lambda _checked=False: self.start_action("stretch"))
        nap_action.triggered.connect(lambda _checked=False: self.start_action("nap"))
        bigger_action.triggered.connect(lambda _checked=False: self.set_pet_height(self.pet_height + 28))
        smaller_action.triggered.connect(lambda _checked=False: self.set_pet_height(self.pet_height - 28))
        wander_action.triggered.connect(self.toggle_wander)
        follow_action.triggered.connect(self.toggle_follow_mouse)
        reset_action.triggered.connect(self.place_near_bottom_right)
        close_action.triggered.connect(QApplication.quit)

        menu.addAction(say_action)
        menu.addAction(jump_action)
        menu.addAction(dance_action)
        menu.addAction(spin_action)
        menu.addAction(shake_action)
        menu.addAction(stretch_action)
        menu.addAction(nap_action)
        menu.addSeparator()
        menu.addAction(bigger_action)
        menu.addAction(smaller_action)
        menu.addSeparator()
        menu.addAction(wander_action)
        menu.addAction(follow_action)
        menu.addSeparator()
        menu.addAction(reset_action)
        menu.addSeparator()
        menu.addAction(close_action)
        menu.exec(event.globalPos())

    def toggle_wander(self, checked: bool) -> None:
        self.wander_enabled = checked
        if not checked:
            self.wander_target = None
        self.say("自动散步：开" if checked else "自动散步：关")

    def toggle_follow_mouse(self, checked: bool) -> None:
        self.follow_mouse = checked
        self.wander_target = None
        self.say("跟随鼠标：开" if checked else "跟随鼠标：关")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transparent desktop pet")
    parser.add_argument("--size", type=int, default=260, help="pet height in pixels, default: 260")
    parser.add_argument("--fps", type=int, default=30, help="animation frames per second, default: 30")
    return parser.parse_args()


def main() -> int:
    # Wayland usually blocks arbitrary transparent always-on-top windows. X11 is smoother for desktop pets.
    if sys.platform.startswith("linux") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"

    args = parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("Character Desktop Pet")

    pet = DesktopPet(resource_path("pet_character.png"), height=args.size, fps=args.fps)
    pet.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
