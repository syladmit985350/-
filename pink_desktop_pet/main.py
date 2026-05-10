"""A tiny animated desktop pet made from the provided image.

Run: python main.py
Requires: PySide6
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)


APP_NAME = "粉毛桌面宠物"
PHRASES = [
    "喵呜~",
    "摸摸头！",
    "带我去玩吧",
    "今天也要加油哦",
    "别忘了休息",
    "我在这里陪你",
]


class DesktopPet(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.app_dir = Path(__file__).resolve().parent
        self.pet_path = self.app_dir / "assets" / "pet.png"
        self.icon_path = self.app_dir / "assets" / "icon.png"

        self.base_pixmap = QPixmap(str(self.pet_path))
        if self.base_pixmap.isNull():
            raise FileNotFoundError(f"Cannot load pet image: {self.pet_path}")

        self.scale = 1.0
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.press_pos = QPoint(0, 0)
        self.phase = 0.0
        self.sleeping = False
        self.wander_enabled = True
        self.always_on_top = True
        self.current_pose: dict[str, float | str] = {}
        self.reaction_frames: list[dict[str, float | str]] = []
        self.reaction_index = 0

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(self.icon_path)))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.label = QLabel(self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.label.setScaledContents(False)

        self.message = QLabel(self)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setStyleSheet(
            "QLabel {"
            "background: rgba(255, 255, 255, 225);"
            "border: 1px solid rgba(255, 150, 190, 190);"
            "border-radius: 10px;"
            "padding: 5px 10px;"
            "font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;"
            "font-size: 12px;"
            "color: #5a3b48;"
            "}"
        )
        self.message.hide()

        self.hide_message_timer = QTimer(self)
        self.hide_message_timer.setSingleShot(True)
        self.hide_message_timer.timeout.connect(self.message.hide)

        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.animate_idle)
        self.idle_timer.start(70)

        self.reaction_timer = QTimer(self)
        self.reaction_timer.timeout.connect(self.advance_reaction)
        self.reaction_timer.setInterval(55)

        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self.wander)
        self.wander_timer.start(5200)

        self.move_anim = QPropertyAnimation(self, b"pos", self)
        self.move_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.update_pet_size()
        self.move_to_start_position()
        self.setup_tray_icon()
        QTimer.singleShot(400, lambda: self.play_reaction("hello"))

    def setup_tray_icon(self) -> None:
        self.tray_icon: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(QIcon(str(self.icon_path)), self)
        tray.setToolTip(APP_NAME)
        menu = QMenu()
        show_action = QAction("显示 / 叫醒", self)
        show_action.triggered.connect(self.show_and_wake)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: self.show_and_wake()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        tray.show()
        self.tray_icon = tray

    def update_pet_size(self) -> None:
        base_width = max(80, int(self.base_pixmap.width() * self.scale))
        base_height = int(self.base_pixmap.height() * (base_width / self.base_pixmap.width()))
        diagonal = int(math.hypot(base_width, base_height) * 1.18)
        self.canvas_width = diagonal
        self.canvas_height = diagonal
        self.setFixedSize(self.canvas_width + 42, self.canvas_height + 70)
        self.render_pet()
        self.position_children()

    def render_pet(self) -> None:
        pose = self.current_pose
        width = max(80, int(self.base_pixmap.width() * self.scale * self.pose_float(pose, "zoom", 1.0)))
        pixmap = self.base_pixmap.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)

        transform = QTransform()
        transform.scale(self.pose_float(pose, "stretch_x", 1.0), self.pose_float(pose, "stretch_y", 1.0))
        transform.rotate(self.pose_float(pose, "tilt", 0.0))
        transformed = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        canvas = QPixmap(self.canvas_width, self.canvas_height)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x = (canvas.width() - transformed.width()) // 2
        y = (canvas.height() - transformed.height()) // 2
        body_rect = QRectF(x, y, transformed.width(), transformed.height())
        self.draw_ground_shadow(painter, body_rect, pose)
        painter.drawPixmap(x, y, transformed)
        self.draw_original_hand_motion(painter, body_rect, transformed, pose)
        self.draw_action_overlay(painter, body_rect, pose)
        painter.end()

        self.label.setPixmap(canvas)
        self.label.resize(canvas.size())

    def pose_float(self, pose: dict[str, float | str], key: str, default: float = 0.0) -> float:
        value = pose.get(key, default)
        return float(value) if isinstance(value, (int, float)) else default

    def pose_gesture(self, pose: dict[str, float | str]) -> str:
        value = pose.get("gesture", "")
        return value if isinstance(value, str) else ""

    def point_at(self, rect: QRectF, x_ratio: float, y_ratio: float) -> QPointF:
        return QPointF(rect.left() + rect.width() * x_ratio, rect.top() + rect.height() * y_ratio)

    def draw_ground_shadow(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        jump = max(0.0, -self.pose_float(pose, "dy", 0.0))
        shadow_width = rect.width() * max(0.48, 0.72 - jump / 130)
        shadow_height = max(4.0, rect.height() * 0.045)
        shadow = QRectF(
            rect.center().x() - shadow_width / 2,
            rect.bottom() - shadow_height * 0.8,
            shadow_width,
            shadow_height,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(120, 70, 95, 42))
        painter.drawEllipse(shadow)

    def draw_action_overlay(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        gesture = self.pose_gesture(pose)
        if self.sleeping:
            gesture = "sleep"
        if not gesture:
            return

        if gesture == "magic":
            self.draw_magic_effects(painter, rect, pose)
        elif gesture == "dance":
            self.draw_dance_effects(painter, rect)
        elif gesture == "cheer":
            self.draw_cheer_effects(painter, rect)
        elif gesture == "stretch":
            self.draw_stretch_effects(painter, rect)
        elif gesture == "sleep":
            self.draw_sleep_marks(painter, rect, pose)
        elif gesture == "pet":
            self.draw_hearts(painter, rect, pose)
        elif gesture == "poke":
            self.draw_poke_marks(painter, rect, pose)
        elif gesture == "jump":
            self.draw_jump_marks(painter, rect, pose)
        elif gesture == "spin":
            self.draw_spin_marks(painter, rect, pose)
        elif gesture == "shy":
            self.draw_shy_marks(painter, rect, pose)

    def hand_region(self, rect: QRectF, side: str) -> QRectF:
        if side == "left":
            return QRectF(
                rect.left() + rect.width() * 0.02,
                rect.top() + rect.height() * 0.41,
                rect.width() * 0.24,
                rect.height() * 0.27,
            )
        return QRectF(
            rect.left() + rect.width() * 0.76,
            rect.top() + rect.height() * 0.4,
            rect.width() * 0.24,
            rect.height() * 0.27,
        )

    def source_hand_region(self, pixmap: QPixmap, side: str) -> QRectF:
        if side == "left":
            return QRectF(
                pixmap.width() * 0.02,
                pixmap.height() * 0.41,
                pixmap.width() * 0.24,
                pixmap.height() * 0.27,
            )
        return QRectF(
            pixmap.width() * 0.76,
            pixmap.height() * 0.4,
            pixmap.width() * 0.24,
            pixmap.height() * 0.27,
        )

    def draw_original_hand_motion(
        self,
        painter: QPainter,
        rect: QRectF,
        transformed: QPixmap,
        pose: dict[str, float | str],
    ) -> None:
        gesture = self.pose_gesture(pose)
        if gesture not in {"wave", "dance", "magic", "stretch", "cheer"}:
            return

        swing = self.pose_float(pose, "swing", 0.0)
        beat = self.pose_float(pose, "beat", 0.0)
        if gesture == "wave":
            self.draw_hand_patch(painter, rect, transformed, "right", -26 * swing, 0.0, -0.15)
            self.draw_motion_arcs(painter, self.point_at(rect, 0.92, 0.28), rect.width() * 0.09, swing)
        elif gesture == "dance":
            self.draw_hand_patch(painter, rect, transformed, "left", -18 * beat, -0.05, -0.1)
            self.draw_hand_patch(painter, rect, transformed, "right", 18 * beat, 0.05, -0.08)
        elif gesture == "magic":
            self.draw_hand_patch(painter, rect, transformed, "right", -32, 0.05, -0.18)
        elif gesture == "stretch":
            self.draw_hand_patch(painter, rect, transformed, "left", -28, -0.03, -0.17)
            self.draw_hand_patch(painter, rect, transformed, "right", 28, 0.03, -0.17)
        elif gesture == "cheer":
            self.draw_hand_patch(painter, rect, transformed, "left", -36, -0.04, -0.2)
            self.draw_hand_patch(painter, rect, transformed, "right", 36, 0.04, -0.2)

    def draw_hand_patch(
        self,
        painter: QPainter,
        rect: QRectF,
        transformed: QPixmap,
        side: str,
        angle: float,
        dx_ratio: float,
        dy_ratio: float,
    ) -> None:
        target = self.hand_region(rect, side)
        source = self.source_hand_region(transformed, side).toRect()
        hand = transformed.copy(source)
        clear_rect = target.adjusted(-rect.width() * 0.02, -rect.height() * 0.02, rect.width() * 0.02, rect.height() * 0.02)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(Qt.GlobalColor.transparent))
        painter.drawRoundedRect(clear_rect, rect.width() * 0.08, rect.width() * 0.08)
        painter.restore()

        center = QPointF(
            target.center().x() + rect.width() * dx_ratio,
            target.center().y() + rect.height() * dy_ratio,
        )
        painter.save()
        painter.translate(center)
        painter.rotate(angle)
        painter.drawPixmap(
            QRectF(-target.width() / 2, -target.height() / 2, target.width(), target.height()),
            hand,
            QRectF(hand.rect()),
        )
        painter.restore()

    def draw_magic_effects(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        pulse = self.pose_float(pose, "pulse", 0.0)
        wand_end = self.point_at(rect, 1.03, 0.11)
        painter.setPen(QPen(QColor(95, 70, 115), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.point_at(rect, 0.92, 0.24), wand_end)
        for i in range(6):
            angle = pulse + i * math.tau / 6
            center = QPointF(
                wand_end.x() + math.cos(angle) * rect.width() * 0.11,
                wand_end.y() + math.sin(angle) * rect.width() * 0.08,
            )
            self.draw_star(painter, center, rect.width() * (0.025 + i % 2 * 0.01), QColor(255, 218, 89))

    def draw_dance_effects(self, painter: QPainter, rect: QRectF) -> None:
        self.draw_music_note(painter, self.point_at(rect, 0.08, 0.13), rect.width() * 0.08)
        self.draw_music_note(painter, self.point_at(rect, 0.9, 0.19), rect.width() * 0.06)

    def draw_stretch_effects(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(QColor(95, 70, 115, 180), 2))
        painter.drawText(self.point_at(rect, 0.82, 0.18), "哈~")

    def draw_cheer_effects(self, painter: QPainter, rect: QRectF) -> None:
        for x, y in [(0.18, 0.03), (0.5, 0.0), (0.82, 0.03)]:
            self.draw_star(painter, self.point_at(rect, x, y), rect.width() * 0.035, QColor(255, 205, 80))

    def draw_sleep_marks(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        painter.setPen(QPen(QColor(120, 91, 150, 190), 2))
        size = max(10, int(rect.width() * 0.08))
        painter.setFont(self.font())
        for i, label in enumerate(["Z", "z", "z"]):
            offset = math.sin(self.phase + i) * 4
            painter.drawText(self.point_at(rect, 0.75 + i * 0.08, 0.08 - i * 0.07 + offset / rect.height()), label)

    def draw_hearts(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        for i, (x, y) in enumerate([(0.17, 0.22), (0.78, 0.18), (0.86, 0.34)]):
            self.draw_heart(painter, self.point_at(rect, x, y), rect.width() * (0.032 + i * 0.006))

    def draw_poke_marks(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        painter.setPen(QPen(QColor(255, 120, 150), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for start, end in [((0.13, 0.35), (0.03, 0.3)), ((0.16, 0.46), (0.04, 0.48)), ((0.82, 0.34), (0.94, 0.28))]:
            painter.drawLine(self.point_at(rect, *start), self.point_at(rect, *end))
        painter.setPen(QPen(QColor(95, 70, 115, 210), 2))
        painter.drawText(self.point_at(rect, 0.75, 0.17), "!")

    def draw_jump_marks(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        painter.setPen(QPen(QColor(255, 160, 80, 180), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(self.point_at(rect, 0.24, 0.92), self.point_at(rect, 0.16, 1.03))
        painter.drawLine(self.point_at(rect, 0.76, 0.92), self.point_at(rect, 0.84, 1.03))

    def draw_spin_marks(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        painter.setPen(QPen(QColor(255, 145, 185, 150), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(rect.left() + rect.width() * 0.05, rect.top() + rect.height() * 0.1, rect.width() * 0.9, rect.height() * 0.72), 30 * 16, 250 * 16)
        self.draw_star(painter, self.point_at(rect, 0.1, 0.2), rect.width() * 0.025, QColor(255, 218, 89))

    def draw_shy_marks(self, painter: QPainter, rect: QRectF, pose: dict[str, float | str]) -> None:
        painter.setPen(QPen(QColor(255, 126, 162, 190), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for y in [0.42, 0.46, 0.5]:
            painter.drawLine(self.point_at(rect, 0.64, y), self.point_at(rect, 0.79, y - 0.02))
            painter.drawLine(self.point_at(rect, 0.21, y), self.point_at(rect, 0.36, y - 0.02))

    def draw_motion_arcs(self, painter: QPainter, center: QPointF, radius: float, swing: float) -> None:
        painter.setPen(QPen(QColor(255, 142, 184, 150), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for i in range(2):
            rect = QRectF(center.x() - radius * (1 + i * 0.28), center.y() - radius, radius * 2, radius * 2)
            painter.drawArc(rect, int((20 + swing * 10) * 16), int(75 * 16))

    def draw_music_note(self, painter: QPainter, pos: QPointF, size: float) -> None:
        painter.setPen(QPen(QColor(120, 86, 150, 190), max(2, int(size * 0.13)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(pos, QPointF(pos.x(), pos.y() - size))
        painter.drawLine(QPointF(pos.x(), pos.y() - size), QPointF(pos.x() + size * 0.5, pos.y() - size * 0.82))
        painter.setBrush(QColor(255, 139, 190, 180))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(pos, size * 0.28, size * 0.2)

    def draw_star(self, painter: QPainter, center: QPointF, radius: float, color: QColor) -> None:
        path = QPainterPath()
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            r = radius if i % 2 == 0 else radius * 0.45
            point = QPointF(center.x() + math.cos(angle) * r, center.y() + math.sin(angle) * r)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

    def draw_heart(self, painter: QPainter, center: QPointF, size: float) -> None:
        path = QPainterPath()
        path.moveTo(center.x(), center.y() + size * 0.55)
        path.cubicTo(center.x() - size * 1.05, center.y() - size * 0.1, center.x() - size * 0.55, center.y() - size * 0.9, center.x(), center.y() - size * 0.35)
        path.cubicTo(center.x() + size * 0.55, center.y() - size * 0.9, center.x() + size * 1.05, center.y() - size * 0.1, center.x(), center.y() + size * 0.55)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 105, 150, 190))
        painter.drawPath(path)

    def position_children(self) -> None:
        pixmap = self.label.pixmap()
        if pixmap is None:
            return
        bob = 0 if self.sleeping else int(math.sin(self.phase) * 5)
        dx = int(self.pose_float(self.current_pose, "dx", 0.0))
        dy = int(self.pose_float(self.current_pose, "dy", 0.0))
        self.label.move((self.width() - pixmap.width()) // 2 + dx, 38 + bob + dy)
        if self.message.isVisible():
            self.message.adjustSize()
            self.message.move((self.width() - self.message.width()) // 2, 4)
            self.message.raise_()

    def animate_idle(self) -> None:
        self.phase += 0.16 if not self.sleeping else 0.05
        if not self.reaction_timer.isActive():
            if self.sleeping:
                self.current_pose = {
                    "tilt": -8,
                    "zoom": 0.96 + math.sin(self.phase) * 0.01,
                    "dy": 5,
                    "gesture": "sleep",
                }
            else:
                self.current_pose = {
                    "tilt": math.sin(self.phase * 0.7) * 2.0,
                    "zoom": 1.0 + math.sin(self.phase) * 0.012,
                }
            self.render_pet()
        self.position_children()

    def reaction(self, name: str) -> list[dict[str, float | str]]:
        reactions = {
            "hello": [
                {"tilt": 0, "zoom": 1.02, "dy": 0, "gesture": "wave", "swing": -1},
                {"tilt": -8, "zoom": 1.04, "dy": -4, "gesture": "wave", "swing": 1},
                {"tilt": 8, "zoom": 1.04, "dy": -4, "gesture": "wave", "swing": -1},
                {"tilt": -6, "zoom": 1.03, "dy": -2, "gesture": "wave", "swing": 1},
                {"tilt": 6, "zoom": 1.03, "dy": -2, "gesture": "wave", "swing": -1},
                {"tilt": 0, "zoom": 1.0, "dy": 0, "gesture": "wave", "swing": 0},
            ],
            "pet": [
                {"tilt": -7, "zoom": 1.04, "stretch_y": 0.96, "dy": 3, "gesture": "pet"},
                {"tilt": 6, "zoom": 1.02, "stretch_y": 0.98, "dy": 1, "gesture": "pet"},
                {"tilt": -5, "zoom": 1.03, "stretch_y": 0.97, "dy": 2, "gesture": "pet"},
                {"tilt": 3, "zoom": 1.01, "dy": 0, "gesture": "pet"},
                {"tilt": 0, "zoom": 1.0, "dy": 0, "gesture": "pet"},
            ],
            "poke": [
                {"tilt": -10, "zoom": 0.98, "dx": -4, "gesture": "poke"},
                {"tilt": 11, "zoom": 1.04, "dx": 5, "gesture": "poke"},
                {"tilt": -8, "zoom": 1.02, "dx": -3, "gesture": "poke"},
                {"tilt": 6, "zoom": 1.01, "dx": 3, "gesture": "poke"},
                {"tilt": 0, "zoom": 1.0, "dx": 0, "gesture": "poke"},
            ],
            "jump": [
                {"zoom": 0.95, "stretch_y": 0.88, "stretch_x": 1.08, "dy": 9, "gesture": "jump"},
                {"zoom": 1.06, "stretch_y": 1.1, "stretch_x": 0.94, "dy": -18, "gesture": "jump"},
                {"zoom": 1.04, "dy": -31, "gesture": "jump"},
                {"zoom": 1.01, "dy": -17, "gesture": "jump"},
                {"zoom": 0.98, "stretch_y": 0.92, "stretch_x": 1.05, "dy": 7, "gesture": "jump"},
                {"zoom": 1.0, "dy": 0, "gesture": "jump"},
            ],
            "spin": [
                {"tilt": 0, "zoom": 1.02, "gesture": "spin"},
                {"tilt": 60, "zoom": 1.04, "gesture": "spin"},
                {"tilt": 130, "zoom": 1.03, "gesture": "spin"},
                {"tilt": 210, "zoom": 1.02, "gesture": "spin"},
                {"tilt": 300, "zoom": 1.03, "gesture": "spin"},
                {"tilt": 360, "zoom": 1.0, "gesture": "spin"},
            ],
            "shy": [
                {"tilt": -8, "zoom": 0.96, "dx": -8, "gesture": "shy"},
                {"tilt": -14, "zoom": 0.9, "dx": -22, "gesture": "shy"},
                {"tilt": -12, "zoom": 0.9, "dx": -28, "gesture": "shy"},
                {"tilt": -6, "zoom": 0.94, "dx": -14, "gesture": "shy"},
                {"tilt": 0, "zoom": 1.0, "dx": 0, "gesture": "shy"},
            ],
            "dance": [
                {"tilt": -7, "zoom": 1.02, "dx": -8, "dy": -4, "gesture": "dance", "beat": -1},
                {"tilt": 7, "zoom": 1.03, "dx": 8, "dy": 2, "gesture": "dance", "beat": 1},
                {"tilt": -10, "zoom": 1.02, "dx": -9, "dy": -5, "gesture": "dance", "beat": 1},
                {"tilt": 10, "zoom": 1.03, "dx": 9, "dy": 2, "gesture": "dance", "beat": -1},
                {"tilt": -6, "zoom": 1.02, "dx": -6, "dy": -3, "gesture": "dance", "beat": 1},
                {"tilt": 6, "zoom": 1.0, "dx": 0, "dy": 0, "gesture": "dance", "beat": -1},
            ],
            "magic": [
                {"tilt": -4, "zoom": 1.01, "gesture": "magic", "pulse": 0},
                {"tilt": 3, "zoom": 1.03, "gesture": "magic", "pulse": 0.8},
                {"tilt": -3, "zoom": 1.04, "gesture": "magic", "pulse": 1.6},
                {"tilt": 4, "zoom": 1.03, "gesture": "magic", "pulse": 2.4},
                {"tilt": 0, "zoom": 1.0, "gesture": "magic", "pulse": 3.2},
            ],
            "stretch": [
                {"zoom": 0.96, "stretch_y": 0.9, "stretch_x": 1.06, "dy": 8, "gesture": "stretch"},
                {"zoom": 1.04, "stretch_y": 1.16, "stretch_x": 0.93, "dy": -12, "gesture": "stretch"},
                {"zoom": 1.05, "stretch_y": 1.18, "stretch_x": 0.92, "dy": -15, "gesture": "stretch"},
                {"zoom": 1.02, "stretch_y": 1.05, "stretch_x": 0.97, "dy": -4, "gesture": "stretch"},
                {"zoom": 1.0, "dy": 0, "gesture": "stretch"},
            ],
            "cheer": [
                {"zoom": 1.0, "dy": 0, "gesture": "cheer"},
                {"zoom": 1.06, "dy": -16, "gesture": "cheer"},
                {"zoom": 1.04, "dy": -24, "gesture": "cheer"},
                {"zoom": 1.02, "dy": -8, "gesture": "cheer"},
                {"zoom": 1.0, "dy": 0, "gesture": "cheer"},
            ],
        }
        return reactions.get(name, reactions["poke"])

    def play_reaction(self, name: str, text: str | None = None) -> None:
        if self.sleeping and name not in {"hello", "poke"}:
            self.show_and_wake()
            return
        self.reaction_frames = self.reaction(name)
        self.reaction_index = 0
        self.reaction_timer.start()
        if text is not None:
            self.say(text)
        elif name == "hello":
            self.say("桌面宠物启动！")
        elif random.random() < 0.7:
            self.say(random.choice(PHRASES), 1500)

    def advance_reaction(self) -> None:
        if self.reaction_index >= len(self.reaction_frames):
            self.reaction_timer.stop()
            self.current_pose = {}
            self.render_pet()
            self.position_children()
            return
        self.current_pose = self.reaction_frames[self.reaction_index]
        self.reaction_index += 1
        self.render_pet()
        self.position_children()

    def say(self, text: str | None = None, timeout_ms: int = 1900) -> None:
        self.message.setText(text or random.choice(PHRASES))
        self.message.show()
        self.position_children()
        self.hide_message_timer.start(timeout_ms)

    def show_and_wake(self) -> None:
        self.sleeping = False
        self.show()
        self.raise_()
        self.activateWindow()
        self.play_reaction("hello", "我回来啦！")

    def move_to_start_position(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.right() - self.width() - 90
        y = geo.bottom() - self.height() - 70
        self.move(max(geo.left(), x), max(geo.top(), y))

    def current_screen_geometry(self):
        center = self.frameGeometry().center()
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        return screen.availableGeometry() if screen else None

    def clamp_to_screen(self, point: QPoint) -> QPoint:
        geo = self.current_screen_geometry()
        if geo is None:
            return point
        x = min(max(point.x(), geo.left()), geo.right() - self.width())
        y = min(max(point.y(), geo.top()), geo.bottom() - self.height())
        return QPoint(x, y)

    def wander(self) -> None:
        if not self.wander_enabled or self.sleeping or self.dragging or not self.isVisible():
            return
        dx = random.randint(-160, 160)
        dy = random.randint(-90, 90)
        target = self.clamp_to_screen(self.pos() + QPoint(dx, dy))
        if target == self.pos():
            return
        self.move_anim.stop()
        self.move_anim.setDuration(random.randint(1300, 2400))
        self.move_anim.setStartValue(self.pos())
        self.move_anim.setEndValue(target)
        self.move_anim.start()
        if random.random() < 0.35:
            self.play_reaction(random.choice(["jump", "pet", "dance", "stretch"]), random.choice(PHRASES))

    def set_scale(self, scale: float) -> None:
        old_center = self.frameGeometry().center()
        self.scale = scale
        self.update_pet_size()
        self.move(self.clamp_to_screen(old_center - QPoint(self.width() // 2, self.height() // 2)))
        self.play_reaction("jump", f"大小：{int(scale * 100)}%")

    def set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top = enabled
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.play_reaction("pet", "已置顶" if enabled else "取消置顶")

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        pet_action = QAction("摸摸她", self)
        pet_action.triggered.connect(lambda checked=False: self.play_reaction("pet", "嘿嘿，好舒服~"))
        menu.addAction(pet_action)

        wave_action = QAction("打个招呼", self)
        wave_action.triggered.connect(lambda checked=False: self.play_reaction("hello", "你好呀！"))
        menu.addAction(wave_action)

        jump_action = QAction("开心跳一下", self)
        jump_action.triggered.connect(lambda checked=False: self.play_reaction("jump", "蹦！"))
        menu.addAction(jump_action)

        spin_action = QAction("转一圈", self)
        spin_action.triggered.connect(lambda checked=False: self.play_reaction("spin", "转圈圈~"))
        menu.addAction(spin_action)

        shy_action = QAction("害羞躲一下", self)
        shy_action.triggered.connect(lambda checked=False: self.play_reaction("shy", "不要一直盯着看啦"))
        menu.addAction(shy_action)

        action_menu = menu.addMenu("动作")
        for title, action_name, text in [
            ("跳舞", "dance", "跟着节拍！"),
            ("施法", "magic", "变出一点好运"),
            ("伸懒腰", "stretch", "哈~ 活过来了"),
            ("加油打气", "cheer", "你超可以！"),
        ]:
            action = QAction(title, self)
            action.triggered.connect(
                lambda checked=False, name=action_name, line=text: self.play_reaction(name, line)
            )
            action_menu.addAction(action)

        menu.addSeparator()
        sleep_action = QAction("睡觉 / 叫醒", self)
        sleep_action.triggered.connect(self.toggle_sleep)
        menu.addAction(sleep_action)

        wander_action = QAction("随机散步", self)
        wander_action.setCheckable(True)
        wander_action.setChecked(self.wander_enabled)
        wander_action.triggered.connect(self.toggle_wander)
        menu.addAction(wander_action)

        top_action = QAction("窗口置顶", self)
        top_action.setCheckable(True)
        top_action.setChecked(self.always_on_top)
        top_action.triggered.connect(self.set_always_on_top)
        menu.addAction(top_action)

        size_menu = menu.addMenu("大小")
        for title, scale in [("80%", 0.8), ("100%", 1.0), ("120%", 1.2), ("150%", 1.5)]:
            action = QAction(title, self)
            action.triggered.connect(lambda checked=False, s=scale: self.set_scale(s))
            size_menu.addAction(action)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        menu.exec(event.globalPos())

    def toggle_wander(self, enabled: bool) -> None:
        self.wander_enabled = enabled
        self.play_reaction("jump" if enabled else "pet", "开始散步" if enabled else "乖乖待着")

    def toggle_sleep(self) -> None:
        self.sleeping = not self.sleeping
        self.reaction_timer.stop()
        if self.sleeping:
            self.move_anim.stop()
            self.current_pose = {"tilt": -8, "zoom": 0.96, "dy": 5, "gesture": "sleep"}
            self.render_pet()
            self.say("Zzz...", 2600)
        else:
            self.play_reaction("hello", "醒啦！")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.move_anim.stop()
            self.press_pos = event.globalPosition().toPoint()
            self.drag_offset = self.press_pos - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            release_pos = event.globalPosition().toPoint()
            moved = (release_pos - self.press_pos).manhattanLength()
            self.dragging = False
            if moved < 8:
                action_name, line = random.choice(
                    [
                        ("poke", "戳到我啦"),
                        ("pet", "嘿嘿，好舒服~"),
                        ("hello", "我在！"),
                        ("cheer", "给你打气！"),
                    ]
                )
                self.play_reaction(action_name, line)
            else:
                self.play_reaction("jump", "这里也不错！")
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_sleep()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    pet = DesktopPet()
    pet.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
