"""
ui/avatar_widget.py
Avatar animado do AURA — personagem sempre visível na área de trabalho.

Estados disponíveis:
  idle      — respiração suave, pulso lento (estado padrão)
  thinking  — rotação de partículas orbitando o núcleo
  speaking  — ondas de áudio irradiando do centro
  working   — engrenagem girando + barra de progresso orbital
  error     — pulso vermelho com tremor

Características:
  - Janela sem bordas, sempre no topo, fundo transparente
  - Arrastável por clique e arraste
  - Clique simples abre/fecha o ChatPanel
  - Animações via QPropertyAnimation + QPainter
  - Thread-safe: set_state() pode ser chamado de qualquer thread via signal
"""

import math
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QObject, QRectF
)
from PyQt6.QtGui import (
    QPainter, QColor, QRadialGradient, QPen,
    QBrush, QPainterPath, QLinearGradient, QFont
)
from config.settings import settings
from core.logger import setup_logger

logger = setup_logger("avatar")

# ── Paleta de cores por estado ────────────────────────────────────────────────
STATE_COLORS = {
    "idle":     {"core": "#4FC3F7", "glow": "#0288D1", "ring": "#29B6F6", "bg": "#0D1B2A"},
    "thinking": {"core": "#CE93D8", "glow": "#7B1FA2", "ring": "#AB47BC", "bg": "#1A0D2A"},
    "speaking": {"core": "#80DEEA", "glow": "#00838F", "ring": "#26C6DA", "bg": "#0D2224"},
    "working":  {"core": "#FFD54F", "glow": "#F57F17", "ring": "#FFCA28", "bg": "#2A1E0D"},
    "error":    {"core": "#EF9A9A", "glow": "#B71C1C", "ring": "#EF5350", "bg": "#2A0D0D"},
}

# ── Sinais thread-safe ────────────────────────────────────────────────────────
class _AvatarSignals(QObject):
    set_state_signal = pyqtSignal(str)
    toggle_chat_signal = pyqtSignal()


class AvatarWidget(QWidget):
    """
    Personagem animado do AURA.
    Fica sempre acima das janelas, pode ser arrastado, clique abre o chat.
    """

    # Sinal emitido ao clicar (para o app.py conectar ao ChatPanel)
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()

        self._signals = _AvatarSignals()
        self._signals.set_state_signal.connect(self._apply_state)

        # Estado atual
        self._state = "idle"
        self._colors = STATE_COLORS["idle"]

        # Variáveis de animação (0.0 → 1.0, controladas por QTimer)
        self._tick: float = 0.0          # relógio geral de animação
        self._pulse: float = 0.0         # amplitude do pulso atual
        self._rotation: float = 0.0      # ângulo das partículas/engrenagem
        self._wave_phase: float = 0.0    # fase das ondas de fala
        self._shake_x: float = 0.0       # tremor do erro

        # Transição de cor suave
        self._color_t: float = 1.0       # 0=cor anterior, 1=cor atual
        self._prev_colors = self._colors

        # Drag
        self._drag_pos: QPoint | None = None

        # Tamanho do avatar
        self._size = settings.get("ui", "avatar_size", default=120)

        self._setup_window()
        self._restore_position()

        # Timer de animação — 60 FPS
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start(16)  # ~60 FPS

        logger.info("AvatarWidget iniciado")

    # ── Configuração da janela ────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool              # não aparece na taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedSize(self._size + 40, self._size + 40)  # margem para o brilho
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _restore_position(self) -> None:
        """Restaura a última posição salva, ou usa o canto inferior direito."""
        pos = settings.get("ui", "avatar_position")
        screen = QApplication.primaryScreen().geometry()

        if pos and len(pos) == 2:
            x = int(pos[0] * screen.width()  / 100)
            y = int(pos[1] * screen.height() / 100)
        else:
            x = screen.width()  - self.width()  - 20
            y = screen.height() - self.height() - 60

        self.move(x, y)

    def _save_position(self) -> None:
        """Persiste a posição atual como porcentagem da tela."""
        screen = QApplication.primaryScreen().geometry()
        pct_x = round(self.x() / screen.width()  * 100, 1)
        pct_y = round(self.y() / screen.height() * 100, 1)
        settings.set("ui", "avatar_position", value=[pct_x, pct_y])

    # ── API pública — thread-safe ─────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """
        Muda o estado visual do avatar.
        Pode ser chamado de qualquer thread.

        Estados: "idle" | "thinking" | "speaking" | "working" | "error"
        """
        if state not in STATE_COLORS:
            logger.warning(f"Estado desconhecido: '{state}'. Usando 'idle'.")
            state = "idle"
        self._signals.set_state_signal.emit(state)

    def _apply_state(self, state: str) -> None:
        """Executa no thread da UI (chamado via signal)."""
        if state == self._state:
            return
        logger.debug(f"Avatar: {self._state} → {state}")
        self._prev_colors = self._colors
        self._state = state
        self._colors = STATE_COLORS[state]
        self._color_t = 0.0  # inicia transição de cor

    # ── Loop de animação ──────────────────────────────────────────────────────

    def _tick_animation(self) -> None:
        dt = 0.016  # segundos por frame

        self._tick += dt

        # Transição suave de cor (dura ~400ms)
        if self._color_t < 1.0:
            self._color_t = min(1.0, self._color_t + dt / 0.4)

        state = self._state

        if state == "idle":
            # Respiração senoidal lenta (ciclo de 3s)
            self._pulse = 0.5 + 0.5 * math.sin(self._tick * 2 * math.pi / 3)

        elif state == "thinking":
            # Pulso médio + rotação de partículas
            self._pulse = 0.6 + 0.4 * math.sin(self._tick * 4)
            self._rotation += dt * 120  # 120 graus/s

        elif state == "speaking":
            # Pulso rápido irregular + fase de onda
            self._pulse = 0.5 + 0.5 * abs(math.sin(self._tick * 8))
            self._wave_phase += dt * 6

        elif state == "working":
            # Rotação constante de engrenagem
            self._pulse = 0.7 + 0.3 * math.sin(self._tick * 3)
            self._rotation += dt * 90

        elif state == "error":
            # Pulso rápido + tremor lateral
            self._pulse = 0.5 + 0.5 * abs(math.sin(self._tick * 12))
            self._shake_x = math.sin(self._tick * 40) * 4 * self._pulse

        self.update()

    # ── Renderização ──────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx = w / 2 + (self._shake_x if self._state == "error" else 0)
        cy = h / 2
        r  = self._size / 2

        # Interpola cor durante transição
        core_color = self._lerp_color(
            self._prev_colors["core"], self._colors["core"], self._color_t
        )
        glow_color = self._lerp_color(
            self._prev_colors["glow"], self._colors["glow"], self._color_t
        )
        ring_color = self._lerp_color(
            self._prev_colors["ring"], self._colors["ring"], self._color_t
        )

        # Despacha o renderer do estado atual
        if self._state == "idle":
            self._draw_idle(painter, cx, cy, r, core_color, glow_color, ring_color)
        elif self._state == "thinking":
            self._draw_thinking(painter, cx, cy, r, core_color, glow_color, ring_color)
        elif self._state == "speaking":
            self._draw_speaking(painter, cx, cy, r, core_color, glow_color, ring_color)
        elif self._state == "working":
            self._draw_working(painter, cx, cy, r, core_color, glow_color, ring_color)
        elif self._state == "error":
            self._draw_error(painter, cx, cy, r, core_color, glow_color, ring_color)

        painter.end()

    # ── Renderers por estado ──────────────────────────────────────────────────

    def _draw_idle(self, p, cx, cy, r, core, glow, ring) -> None:
        """Respiração suave — núcleo pulsante + anel simples."""
        pulse = self._pulse
        nr = r * (0.55 + 0.10 * pulse)  # núcleo respira

        # Brilho externo
        self._draw_glow(p, cx, cy, r * (0.9 + 0.1 * pulse), glow, alpha=60)

        # Anel externo
        pen = QPen(QColor(ring), 2.5)
        pen.setStyle(Qt.PenStyle.SolidLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r * 0.85, cy - r * 0.85, r * 1.7, r * 1.7))

        # Núcleo gradiente
        self._draw_core(p, cx, cy, nr, core, glow)

        # Pontinhos de "respiração" no anel
        for i in range(8):
            angle = math.radians(i * 45 + self._tick * 20)
            bx = cx + math.cos(angle) * r * 0.85
            by = cy + math.sin(angle) * r * 0.85
            dot_r = 2.5 * (0.5 + 0.5 * pulse) if i % 2 == 0 else 1.5
            c = QColor(ring)
            c.setAlpha(120 + int(100 * pulse))
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(bx - dot_r, by - dot_r, dot_r * 2, dot_r * 2))

    def _draw_thinking(self, p, cx, cy, r, core, glow, ring) -> None:
        """Partículas orbitando o núcleo."""
        pulse = self._pulse
        rot   = self._rotation

        # Brilho
        self._draw_glow(p, cx, cy, r * 0.85, glow, alpha=80)

        # 3 anéis orbitais em velocidades diferentes
        for orbit_idx, (orbit_r, n_particles, speed_mult) in enumerate([
            (r * 0.72, 3, 1.0),
            (r * 0.88, 5, 0.6),
            (r * 0.58, 2, 1.5),
        ]):
            for i in range(n_particles):
                angle = math.radians(rot * speed_mult + i * (360 / n_particles))
                px = cx + math.cos(angle) * orbit_r
                py = cy + math.sin(angle) * orbit_r
                pr = 4.5 if orbit_idx == 0 else (3.0 if orbit_idx == 1 else 3.5)
                c = QColor(ring)
                # Opacidade baseada na posição angular (efeito de profundidade)
                alpha_base = 160 + int(80 * math.cos(angle))
                c.setAlpha(max(60, alpha_base))
                p.setBrush(QBrush(c))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(px - pr, py - pr, pr * 2, pr * 2))

        # Núcleo menor + pulsante
        self._draw_core(p, cx, cy, r * (0.40 + 0.08 * pulse), core, glow)

        # "..." de pensamento acima
        self._draw_thinking_dots(p, cx, cy - r * 0.68)

    def _draw_thinking_dots(self, p, cx, cy) -> None:
        """Três pontinhos animados de 'pensando...'"""
        for i in range(3):
            phase = self._tick * 5 + i * 0.8
            alpha = int(80 + 160 * abs(math.sin(phase)))
            dot_r = 3.5
            dx = cx + (i - 1) * 11
            c = QColor(self._colors["ring"])
            c.setAlpha(alpha)
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(dx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2))

    def _draw_speaking(self, p, cx, cy, r, core, glow, ring) -> None:
        """Ondas sonoras irradiando do centro."""
        pulse = self._pulse
        phase = self._wave_phase

        # Ondas concêntricas expandindo
        for i in range(4):
            wave_r = r * (0.45 + i * 0.16 + 0.06 * math.sin(phase - i * 1.2))
            alpha  = max(0, int(180 - i * 45) - int(40 * pulse))
            c = QColor(ring)
            c.setAlpha(alpha)
            pen = QPen(c, 2.0 - i * 0.3)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - wave_r, cy - wave_r, wave_r * 2, wave_r * 2))

        # Barra de equalizer na base do avatar
        self._draw_eq_bars(p, cx, cy + r * 0.60, ring, pulse)

        # Núcleo
        self._draw_core(p, cx, cy, r * (0.42 + 0.10 * pulse), core, glow)

    def _draw_eq_bars(self, p, cx, base_y, ring, pulse) -> None:
        """Mini equalizador de áudio."""
        n_bars = 7
        bar_w  = 4
        spacing = 7
        total_w = n_bars * spacing
        for i in range(n_bars):
            height = 6 + 10 * abs(math.sin(self._wave_phase * 2 + i * 0.9)) * pulse
            bx = cx - total_w / 2 + i * spacing
            c = QColor(ring)
            c.setAlpha(200)
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(
                QRectF(bx - bar_w / 2, base_y - height, bar_w, height), 2, 2
            )

    def _draw_working(self, p, cx, cy, r, core, glow, ring) -> None:
        """Engrenagem girando + arco de progresso orbital."""
        rot = self._rotation
        pulse = self._pulse

        # Brilho âmbar
        self._draw_glow(p, cx, cy, r * 0.85, glow, alpha=70)

        # Arco de progresso girando (indica trabalho contínuo)
        arc_rect = QRectF(cx - r * 0.82, cy - r * 0.82, r * 1.64, r * 1.64)
        pen = QPen(QColor(ring), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Arco de 270° girando
        start_angle = int(rot * 16)  # Qt usa 1/16 graus
        span_angle  = 270 * 16
        p.drawArc(arc_rect, start_angle, span_angle)

        # Dentes da engrenagem
        self._draw_gear(p, cx, cy, r * 0.52, rot, ring)

        # Núcleo
        self._draw_core(p, cx, cy, r * (0.30 + 0.06 * pulse), core, glow)

    def _draw_gear(self, p, cx, cy, radius, rot_deg, ring) -> None:
        """Engrenagem com 8 dentes."""
        n_teeth = 8
        tooth_h = radius * 0.28
        tooth_w = math.radians(360 / n_teeth) * 0.38

        path = QPainterPath()
        first = True
        for i in range(n_teeth * 2):
            r_use = radius + tooth_h if i % 2 == 0 else radius
            angle = math.radians(rot_deg + i * 180 / n_teeth)
            px = cx + math.cos(angle) * r_use
            py = cy + math.sin(angle) * r_use
            if first:
                path.moveTo(px, py)
                first = False
            else:
                path.lineTo(px, py)
        path.closeSubpath()

        c = QColor(ring)
        c.setAlpha(180)
        p.setBrush(QBrush(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

    def _draw_error(self, p, cx, cy, r, core, glow, ring) -> None:
        """Pulso vermelho intenso + sinal de exclamação."""
        pulse = self._pulse

        # Brilho vermelho intenso pulsante
        self._draw_glow(p, cx, cy, r * (0.9 + 0.15 * pulse), glow, alpha=int(100 * pulse))

        # Anel externo com tracejado vermelho
        pen = QPen(QColor(ring), 3, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r * 0.87, cy - r * 0.87, r * 1.74, r * 1.74))

        # Núcleo vermelho
        self._draw_core(p, cx, cy, r * (0.50 + 0.10 * pulse), core, glow)

        # "!" dentro do núcleo
        self._draw_exclamation(p, cx, cy, r)

    def _draw_exclamation(self, p, cx, cy, r) -> None:
        """Símbolo '!' centralizado no avatar de erro."""
        font = QFont("Arial", int(r * 0.38), QFont.Weight.Bold)
        p.setFont(font)
        c = QColor("#FFFFFF")
        c.setAlpha(int(180 + 75 * self._pulse))
        p.setPen(QPen(c))
        rect = QRectF(cx - r * 0.5, cy - r * 0.55, r, r)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "!")

    # ── Primitivas reutilizáveis ──────────────────────────────────────────────

    def _draw_core(self, p, cx, cy, radius, core_hex, glow_hex) -> None:
        """Círculo central com gradiente radial."""
        grad = QRadialGradient(cx, cy - radius * 0.2, radius)
        c_inner = QColor(core_hex)
        c_inner.setAlpha(255)
        c_outer = QColor(glow_hex)
        c_outer.setAlpha(200)
        grad.setColorAt(0.0, c_inner)
        grad.setColorAt(0.6, c_outer)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

    def _draw_glow(self, p, cx, cy, radius, glow_hex, alpha=80) -> None:
        """Halo de brilho externo difuso."""
        grad = QRadialGradient(cx, cy, radius)
        c = QColor(glow_hex)
        c.setAlpha(alpha)
        grad.setColorAt(0.0, c)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

    @staticmethod
    def _lerp_color(hex_a: str, hex_b: str, t: float) -> str:
        """Interpola linearmente entre duas cores hex."""
        a = QColor(hex_a)
        b = QColor(hex_b)
        r = int(a.red()   + (b.red()   - a.red())   * t)
        g = int(a.green() + (b.green() - a.green()) * t)
        b_ = int(a.blue() + (b.blue()  - a.blue())  * t)
        return QColor(r, g, b_).name()

    # ── Eventos de mouse (drag + clique) ─────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # Distingue clique (sem arrastar) de drag
            if self._drag_pos is not None:
                delta = event.globalPosition().toPoint() - self._drag_pos - self.frameGeometry().topLeft()
                if abs(delta.x()) < 5 and abs(delta.y()) < 5:
                    self.clicked.emit()
            self._drag_pos = None
            self._save_position()

    def mouseDoubleClickEvent(self, event) -> None:
        # Duplo clique também abre/fecha o chat
        self.clicked.emit()
