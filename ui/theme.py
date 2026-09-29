"""ThemeManager — builds a complete QSS sheet per palette and applies it globally.

Colours are never literal in the QSS; they interpolate tokens. Two complete
sheets are produced rather than string-substituting one, and every interactive
state is styled: default, hover, pressed, focus, checked, disabled.
"""

from PyQt6.QtCore import QEvent, QObject, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from . import tokens as T


def build_qss(c):
    """Return a full stylesheet for the palette `c`."""
    r, s = T.RADIUS, T.SPACE
    card_pad = T.CARD_PADDING
    return f"""
/* --- base ------------------------------------------------------------- */
QWidget {{
    font-family: {T.FONT_UI};
    font-size: {T.TYPO['body'][0]}px;
    color: {c['text']};
}}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolTip {{
    background: {c['surface_variant']};
    color: {c['text']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['md']}px;
    padding: {s['sm']}px {s['md']}px;
}}

/* --- cards ------------------------------------------------------------ */
QFrame[class="card"] {{
    background: {c['surface']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['card']}px;
}}
QFrame[class="rail"] {{
    background: {c['surface']};
    border: none;
    border-right: 1px solid {c['outline_variant']};
}}
QFrame[class="topbar"] {{
    background: {c['surface_glass']};
    border: none;
    border-bottom: 1px solid {c['outline_variant']};
}}
QFrame[class="thumb"] {{
    background: {c['surface_variant']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['card']}px;
}}
QFrame[class="thumb"][selected="true"] {{ border: 2px solid {c['primary']}; }}
QFrame[class="divider"] {{ background: {c['outline_variant']}; border: none; }}
/* Advisor chat bubbles - a role-tinted variant of the plain card, so a user
   turn and the advisor's reply stay visually distinct on scroll-back. */
QFrame[class="card"][bubbleRole="user"] {{
    background: {c['primary_fixed']};
    border: 1px solid {c['primary']};
}}
QFrame[class="card"][bubbleRole="assistant"] {{
    background: {c['surface_variant']};
    border: 1px solid {c['outline_variant']};
}}

QGroupBox {{
    background: {c['surface']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['card']}px;
    margin-top: 16px;
    padding: {card_pad}px {s['md']}px {s['md']}px {s['md']}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {s['md']}px;
    padding: 0 {s['xs']}px;
    color: {c['text_muted']};
    font-size: {T.TYPO['label'][0]}px;
    font-weight: {T.TYPO['label'][1]};
}}

/* --- navigation rail -------------------------------------------------- */
QToolButton[class="nav"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r['md']}px;
    padding: {s['sm']}px {s['md']}px;
    color: {c['text_muted']};
    font-size: {T.TYPO['body'][0]}px;
    font-weight: 500;
    text-align: left;
}}
QToolButton[class="nav"]:hover {{
    background: {c['surface_variant']};
    color: {c['text']};
}}
QToolButton[class="nav"]:pressed {{ background: {c['surface_variant_high']}; }}
QToolButton[class="nav"]:checked {{
    background: {c['primary_fixed']};
    color: {c['primary']};
    font-weight: 600;
    border: 1px solid {c['primary']};
}}

/* --- buttons ---------------------------------------------------------- */
QPushButton {{
    background: {c['surface_variant']};
    color: {c['text']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['md']}px;
    padding: {s['sm']}px {s['md']}px;
    font-size: {T.TYPO['body_sm'][0]}px;
    font-weight: 600;
    min-height: 20px;
}}
QPushButton:hover {{ background: {c['surface_variant_high']}; border-color: {c['outline']}; }}
QPushButton:pressed {{ background: {c['surface_variant']}; }}
QPushButton:focus {{ border: 1px solid {c['primary']}; }}
QPushButton:disabled {{
    background: {c['bg']}; color: {c['text_muted']}; border-color: {c['outline_variant']};
}}
QPushButton[class="primary"] {{
    background: {c['primary_gradient']}; color: {c['on_primary']}; border-color: {c['primary']};
    font-weight: 700;
}}
QPushButton[class="primary"]:hover {{
    background: {c['primary_container']}; border-color: {c['primary_container']};
}}
QPushButton[class="primary"]:pressed {{ background: {c['primary']}; }}
QPushButton[class="primary"]:disabled {{
    background: {c['surface_variant']}; color: {c['text_muted']}; border-color: {c['outline_variant']};
}}
QPushButton[class="ghost"] {{ background: transparent; border-color: transparent; }}
QPushButton[class="ghost"]:hover {{ background: {c['surface_variant']}; }}
QPushButton[class="danger"] {{
    background: transparent; color: {c['error']}; border-color: {c['error']};
}}
QPushButton[class="danger"]:hover {{ background: {c['error']}; color: {c['text']}; }}

/* A pill toggle - Influencer Studio's Age Range/Style/Hair/Eye pickers. Same
   checked look as the nav rail's own checked chip (primary_fixed background,
   primary text and border) rather than the gradient, which stays reserved
   for one CTA per view. */
QPushButton[class="chip"] {{
    background: {c['surface_variant']};
    color: {c['text']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['pill']}px;
    padding: {s['xs']}px {s['md']}px;
    font-size: {T.TYPO['body_sm'][0]}px;
    font-weight: 600;
    min-height: 18px;
}}
QPushButton[class="chip"]:hover {{ border-color: {c['outline']}; }}
QPushButton[class="chip"]:checked {{
    background: {c['primary_fixed']};
    color: {c['primary']};
    border: 1px solid {c['primary']};
    font-weight: 700;
}}

QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {r['md']}px;
    padding: {s['xs']}px {s['sm']}px;
    color: {c['text']};
}}
QToolButton:hover {{ background: {c['surface_variant']}; }}
QToolButton:pressed {{ background: {c['surface_variant_high']}; }}
QToolButton[class="star"] {{ padding: 1px; border: none; background: transparent; }}
QToolButton[class="star"]:hover {{ background: transparent; }}

/* --- inputs ----------------------------------------------------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background: {c['surface_variant']};
    color: {c['text']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['md']}px;
    padding: {s['sm']}px {s['sm']}px;
    selection-background-color: {c['primary_fixed']};
    selection-color: {c['text']};
}}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover {{
    border-color: {c['outline']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c['primary']};
}}
QLineEdit[hasError="true"], QPlainTextEdit[hasError="true"] {{
    border: 1px solid {c['error']};
}}
QLineEdit[class="search"] {{
    background: {c['bg']};
    border-radius: {r['pill']}px;
    padding: {s['sm']}px {s['md']}px;
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background: {c['bg']}; color: {c['text_muted']};
}}
QPlainTextEdit[class="mono"] {{ font-family: {T.FONT_MONO}; font-size: 13px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {c['surface']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['md']}px;
    selection-background-color: {c['primary_fixed']};
    selection-color: {c['text']};
    outline: none;
    padding: {s['xs']}px;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; border: none; }}
QCheckBox {{ spacing: {s['sm']}px; color: {c['text']}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: {r['sm']}px;
    border: 1px solid {c['outline']};
    background: {c['surface_variant']};
}}
QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; }}
QCheckBox::indicator:hover {{ border-color: {c['primary']}; }}

/* --- lists, trees, tables --------------------------------------------- */
QListWidget, QTreeWidget, QTableWidget {{
    background: {c['surface_variant']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['md']}px;
    alternate-background-color: {c['surface']};
    outline: none;
    gridline-color: {c['outline_variant']};
}}
QListWidget::item, QTreeWidget::item, QTableWidget::item {{
    padding: {s['sm']}px;
    border-radius: {r['sm']}px;
}}
QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover {{
    background: {c['surface_variant_high']};
}}
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background: {c['primary_fixed']}; color: {c['text']};
}}
QHeaderView::section {{
    background: {c['surface']};
    color: {c['text_muted']};
    border: none;
    border-bottom: 1px solid {c['outline_variant']};
    padding: {s['sm']}px;
    font-size: {T.TYPO['label'][0]}px;
    font-weight: {T.TYPO['label'][1]};
}}
QTableWidget {{ selection-background-color: {c['primary_fixed']}; }}

/* --- chrome ----------------------------------------------------------- */
QMenuBar {{ background: {c['surface']}; color: {c['text']}; border: none; }}
/* `xs` vertically, not `sm`. This rule was written before the app had a menu
   bar to style, so its padding was never measured against anything. Once one
   existed it stood 33px tall and took that much off the canvas, which at the
   1100x700 minimum was enough to compress Compose's character-library card
   until Load/Save and New/Delete overlapped by one to three pixels. Raising
   the window minimum instead would have pushed it past what a 1366x768 laptop
   can show, so the chrome gives the pixels back. Horizontal padding is
   untouched - the menu titles still have room to breathe. */
QMenuBar::item {{ padding: {s['xs']}px {s['md']}px; border-radius: {r['sm']}px; }}
QMenuBar::item:selected {{ background: {c['surface_variant']}; }}
QMenu {{
    background: {c['surface']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['md']}px;
    padding: {s['xs']}px;
}}
QMenu::item {{ padding: {s['sm']}px {s['md']}px; border-radius: {r['sm']}px; }}
QMenu::item:selected {{ background: {c['primary_fixed']}; color: {c['text']}; }}
QStatusBar {{
    background: {c['surface']};
    color: {c['text_muted']};
    border-top: 1px solid {c['outline_variant']};
}}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: {c['outline_variant']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QProgressBar {{
    background: {c['surface_variant']};
    border: none;
    border-radius: {r['sm']}px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {c['primary']}; border-radius: {r['sm']}px; }}

/* --- scrollbars ------------------------------------------------------- */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {c['outline']}; border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:horizontal {{
    background: {c['outline']}; border-radius: 4px; min-width: 28px;
}}
QScrollBar::handle:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --- typography classes ----------------------------------------------- */
QLabel[class="hero"] {{
    font-size: {T.TYPO['hero'][0]}px; font-weight: {T.TYPO['hero'][1]};
}}
QLabel[class="display"] {{
    font-size: {T.TYPO['display'][0]}px; font-weight: {T.TYPO['display'][1]};
}}
QLabel[class="headline"] {{
    font-size: {T.TYPO['headline'][0]}px; font-weight: {T.TYPO['headline'][1]};
}}
QLabel[class="title"] {{
    font-size: {T.TYPO['title'][0]}px; font-weight: {T.TYPO['title'][1]};
}}
QLabel[class="muted"] {{
    color: {c['text_muted']}; font-size: {T.TYPO['body_sm'][0]}px;
}}
QLabel[class="caption"] {{
    color: {c['text_muted']}; font-size: {T.TYPO['caption'][0]}px;
    font-weight: {T.TYPO['caption'][1]};
}}
QLabel[class="brand"] {{
    color: {c['primary']}; font-size: {T.TYPO['title'][0]}px; font-weight: 700;
}}
QLabel[class="preview"] {{
    background: {c['bg']};
    border: 1px dashed {c['outline']};
    border-radius: {r['card']}px;
    color: {c['text_muted']};
}}

/* --- tabs ------------------------------------------------------------- */
QTabWidget::pane {{
    background: {c['surface']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['card']}px;
    top: -1px;
}}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {c['text_muted']};
    border: 1px solid transparent;
    border-top-left-radius: {r['md']}px;
    border-top-right-radius: {r['md']}px;
    /* Tight horizontal padding: five section tabs have to fit the sidebar. */
    padding: {s['sm']}px {s['sm']}px;
    margin-right: 2px;
    font-size: {T.TYPO['caption'][0]}px;
    font-weight: 600;
}}
QTabBar::tab:hover {{ background: {c['surface_variant']}; color: {c['text']}; }}
QTabBar::tab:selected {{
    background: {c['surface']};
    color: {c['primary']};
    border-color: {c['outline_variant']};
    border-bottom-color: {c['surface']};
}}
QTabBar::tab:disabled {{ color: {c['outline']}; }}

/* --- badges ----------------------------------------------------------- */
QLabel[class="badge"] {{
    border-radius: {r['pill']}px;
    padding: {s['xs']}px {s['md']}px;
    font-size: {T.TYPO['label'][0]}px;
    font-weight: {T.TYPO['label'][1]};
    color: {c['on_primary']};
    background: {c['text_muted']};
}}
QLabel[class="badge"][status="success"] {{ background: {c['success']}; }}
QLabel[class="badge"][status="warning"] {{ background: {c['warning']}; }}
QLabel[class="badge"][status="danger"]  {{ background: {c['error']}; }}
QLabel[class="badge"][status="accent"]  {{
    background: {c['primary_gradient']}; color: {c['on_primary']};
}}

/* --- glass surfaces ----------------------------------------------------- */
QFrame[class="glass"] {{
    background: {c['surface_glass']};
    border: 1px solid {c['outline_variant']};
    border-radius: {r['xl']}px;
}}
"""


def repolish(widget):
    """Re-evaluate QSS after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def elevate(widget, blur=24, alpha=0.35, dy=2, color=None):
    """Soft depth for a card. Subtle, never a heavy drop shadow.

    `color` overrides the default black shadow with a tint — used for the
    accent glow behind a checked nav item rather than a second helper.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(color or QColor(0, 0, 0, int(255 * alpha)))
    widget.setGraphicsEffect(effect)
    return effect


class _HoverElevate(QObject):
    """Animates a drop shadow's blur on enter/leave instead of `widget`'s own
    geometry — Qt's layouts fight (and win) any animation that changes a
    layout-managed widget's size or position, so "hover lift" here means the
    shadow growing under a widget that itself never moves.
    """

    def __init__(self, widget, base_blur, hover_blur, dy, color):
        super().__init__(widget)
        self.widget = widget
        self.base_blur = base_blur
        self.hover_blur = hover_blur
        self.effect = QGraphicsDropShadowEffect(widget)
        self.effect.setOffset(0, dy)
        self.effect.setColor(color)
        self.effect.setBlurRadius(base_blur)
        widget.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"blurRadius", self)
        self.anim.setDuration(T.MOTION_FAST)

    def eventFilter(self, obj, event):
        if obj is self.widget:
            if event.type() == QEvent.Type.Enter:
                self._animate_to(self.hover_blur)
            elif event.type() == QEvent.Type.Leave:
                self._animate_to(self.base_blur)
        return False

    def _animate_to(self, value):
        self.anim.stop()
        self.anim.setStartValue(self.effect.blurRadius())
        self.anim.setEndValue(value)
        self.anim.start()


def hover_elevate(widget, base_blur=14, hover_blur=30, dy=3, alpha=0.30, color=None):
    """Card-hover motion: the shadow lifts on enter, settles on leave.

    Returns the handler so a caller can hold a reference if it wants to, but
    also stashes one on the widget itself — an installed QObject event filter
    with no other reference is a common source of "the animation just stopped
    working" once the local variable that created it goes out of scope.
    """
    tint = color or QColor(0, 0, 0, int(255 * alpha))
    handler = _HoverElevate(widget, base_blur, hover_blur, dy, tint)
    widget.installEventFilter(handler)
    widget._hover_elevate = handler
    return handler


def pulse(widget, color=None, min_blur=8, max_blur=26, duration=900):
    """A looping glow while `widget` represents work in progress.

    Stop it by calling `.stop()` on the returned QPropertyAnimation (its
    finished/failed signal handler is the natural place) — an un-stopped loop
    keeps animating a hidden or destroyed widget's graphics effect forever.
    """
    tint = color or QColor(56, 189, 248, 140)
    effect = QGraphicsDropShadowEffect(widget)
    effect.setOffset(0, 0)
    effect.setColor(tint)
    effect.setBlurRadius(min_blur)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"blurRadius", widget)
    anim.setDuration(duration)
    anim.setStartValue(min_blur)
    anim.setKeyValueAt(0.5, max_blur)
    anim.setEndValue(min_blur)
    anim.setLoopCount(-1)
    anim.start()
    return anim


class ThemeManager(QObject):
    """Owns the active theme and pushes a complete sheet to the application."""

    changed = pyqtSignal(str)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        self._name = T.DEFAULT_THEME
        self._sheets = {name: build_qss(p) for name, p in T.PALETTES.items()}

    @property
    def name(self):
        return self._name

    @property
    def palette(self):
        return T.PALETTES[self._name]

    @staticmethod
    def detect():
        """The app is dark-first; the OS only decides if it says light."""
        try:
            from PyQt6.QtCore import Qt

            scheme = QGuiApplication.styleHints().colorScheme()
            return "light" if scheme == Qt.ColorScheme.Light else "dark"
        except (AttributeError, TypeError):
            return T.DEFAULT_THEME

    def apply(self, name):
        if name not in self._sheets:
            name = T.DEFAULT_THEME
        self._name = name
        self._app.setStyleSheet(self._sheets[name])
        self.changed.emit(name)

    def toggle(self):
        self.apply("light" if self._name == "dark" else "dark")
