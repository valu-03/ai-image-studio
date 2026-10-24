"""Reusable components — the shared vocabulary the views are built from.

Each styles itself through dynamic QSS properties rather than inline
stylesheets, so a theme switch repaints it with no extra work.
"""

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import assets, tokens as T
from .theme import color as theme_color
from .theme import elevate, hover_elevate, repolish


class Card(QFrame):
    """A rounded surface with generous inner padding.

    Carries a permanent, static soft shadow (`elevate`) for depth — this was a
    defined-but-never-called helper before; every card in the app now actually
    uses it, which is most of what makes the flat original look higgsfield-flat.
    """

    def __init__(self, parent=None, padding=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        pad = T.CARD_PADDING if padding is None else padding
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(pad, pad, pad, pad)
        self.body.setSpacing(T.SPACE["md"])
        elevate(self, blur=20, alpha=0.22, dy=1)


class Badge(QLabel):
    """A status chip. `set_status` uses the property + repolish pattern."""

    def __init__(self, text="", status="neutral", parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "badge")
        self.setProperty("status", status)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A chip hugs its text — it must not stretch to fill a column layout.
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_status(self, status, text=None):
        if text is not None:
            self.setText(text)
        self.setProperty("status", status)
        repolish(self)


class BadgeButton(QPushButton):
    """A badge you can press: same pill and statuses as Badge, but a real button
    - focusable, Enter/Space work, a pointer on hover, read as a button by a
    screen reader. The credits balance used to be a QLabel with a patched
    mousePressEvent: clickable by mouse only, invisible to the keyboard."""

    def __init__(self, text="", status="neutral", parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "badge")
        self.setProperty("status", status)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_status(self, status, text=None):
        if text is not None:
            self.setText(text)
        self.setProperty("status", status)
        repolish(self)


class MutedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "muted")
        self.setWordWrap(True)


class TitleLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "title")


class NavButton(QToolButton):
    """A rail entry: icon + label, checkable, swaps to the accent icon when on."""

    def __init__(self, key, text, parent=None):
        super().__init__(parent)
        self.key = key
        self.setText("  " + text)
        self.setProperty("class", "nav")
        self.setCheckable(True)
        self.setIconSize(assets.NAV_ICON_SIZE)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(text)
        self._refresh_icon()
        self.toggled.connect(lambda _: self._refresh_icon())
        self.toggled.connect(self._refresh_glow)
        self._refresh_glow(self.isChecked())

    def _refresh_icon(self):
        self.setIcon(assets.icon(self.key, active=self.isChecked()))

    def _refresh_glow(self, checked):
        # A soft accent-tinted glow behind the active item — the checked chip
        # alone (background + border) reads as "selected" but flat; this is
        # the one place a genuine glow effect is legible against small text
        # rather than fighting for contrast with it.
        if checked:
            elevate(self, blur=22, dy=0, color=theme_color("glow_primary"))
        else:
            self.setGraphicsEffect(None)


class StarRating(QWidget):
    """1-5 outcome rating. Emits `rated` with the chosen value."""

    rated = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._buttons = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for index in range(1, 6):
            button = QToolButton()
            button.setProperty("class", "star")
            button.setIconSize(assets.STAR_ICON_SIZE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip("Rate {}/5".format(index))
            button.clicked.connect(lambda _=False, v=index: self.set_value(v, emit=True))
            layout.addWidget(button)
            self._buttons.append(button)
        layout.addStretch(1)
        self._paint()

    def value(self):
        return self._value

    def set_value(self, value, emit=False):
        self._value = max(0, min(5, int(value)))
        self._paint()
        if emit:
            self.rated.emit(self._value)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        for button in self._buttons:
            button.setEnabled(enabled)

    def _paint(self):
        for index, button in enumerate(self._buttons, start=1):
            button.setIcon(assets.icon("star", active=index <= self._value))


class ImagePreview(QLabel):
    """Scaled image display that keeps aspect ratio on resize.

    The scaled pixmap must never drive the widget's size hint. A QLabel reports
    its pixmap's size as its size hint, so a label that scales its pixmap to fit
    itself hands its layout a hint that grows on every pass — and the layout
    answers by making it bigger still. Inside a resizable QScrollArea that never
    converges: measured with a 9:16 image (the TikTok/Reels default) it climbs
    until Qt dies, and with mixed aspect ratios it settles with whichever column
    holds the widest image several hundred pixels wider than its neighbours.

    So both hints are pinned to the declared minimum, which nothing about the
    image can change, and the pixmap is fitted into contentsRect() instead.
    """

    def __init__(self, placeholder="No image yet", parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._placeholder = placeholder
        self.setProperty("class", "preview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # QLabel defaults to no wrap - the placeholder text has one deliberate
        # \n, but without this a narrow column truncates the rest of either
        # line mid-word instead of reflowing it onto a new one.
        self.setWordWrap(True)
        # Small enough that a card holding one can always still shrink. A 240px
        # floor made the Brief view's card taller than a 700px window could
        # give it, and Qt resolves that by overlapping the items. The size
        # policy is Expanding, so this costs nothing when there is room.
        self.setMinimumSize(QSize(160, 120))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setText(placeholder)

    # The two overrides that break the feedback loop. Both must be given: Qt
    # consults minimumSizeHint() when a layout is deciding how small a cell may
    # be, and QLabel's own answer to that also follows the pixmap.
    def sizeHint(self):
        return QSize(self.minimumSize())

    def minimumSizeHint(self):
        return QSize(self.minimumSize())

    def clear_image(self):
        self._pixmap = None
        self.setText(self._placeholder)

    def load(self, path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.clear_image()
            return False
        self._pixmap = pixmap
        self._rescale()
        return True

    def _rescale(self):
        if self._pixmap is None:
            return
        # contentsRect(), not size(): the QSS gives this widget a border, and
        # scaling to the full size lets the image sit under it.
        area = self.contentsRect().size()
        if area.width() <= 0 or area.height() <= 0:
            return
        self.setPixmap(self._pixmap.scaled(
            area,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class ResultCard(QFrame):
    """One generated result: a status ribbon, a thumbnail, a caption, a rating.

    The shared shape adopted in place of the app's previous three independent
    thumbnail/status/rating combinations (Compose's preview + badge, Variants'
    old `ThumbCard`, Cats' storyboard tiles) — see the rebuild plan's rollout
    order for which section adopts it in which phase. `ThumbCard` itself was
    removed once Variants (its only caller) switched to this instead; keeping
    both was the exact "3 near-identical widgets" duplication this replaces.
    """

    clicked = pyqtSignal(int)
    rated = pyqtSignal(int, int)   # index, stars

    def __init__(self, index, caption="", parent=None):
        super().__init__(parent)
        self.index = index
        self.setProperty("class", "thumb")
        self.setProperty("selected", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(QSize(190, 260))

        self.status = Badge("queued", "neutral")
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addWidget(self.status)
        status_row.addStretch(1)

        self.preview = ImagePreview("queued")
        self.preview.setMinimumSize(QSize(160, 160))
        self.caption_label = MutedLabel(caption)
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rating = StarRating()
        self.rating.rated.connect(lambda value: self.rated.emit(self.index, value))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.SPACE["sm"], T.SPACE["sm"], T.SPACE["sm"], T.SPACE["sm"])
        layout.setSpacing(T.SPACE["xs"])
        layout.addLayout(status_row)
        layout.addWidget(self.preview, 1)
        layout.addWidget(self.caption_label)
        layout.addWidget(self.rating)
        hover_elevate(self, base_blur=10, hover_blur=26, dy=4)

    def set_status(self, status, text):
        self.status.set_status(status, text)

    def set_image(self, path):
        return self.preview.load(path)

    def set_selected(self, selected):
        self.setProperty("selected", "true" if selected else "false")
        repolish(self)

    def set_caption(self, text):
        self.caption_label.setText(text)

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)
        super().mousePressEvent(event)


class AiSuggestionBadge(QWidget):
    """One shared shape for "call an LLM, offer to apply what came back."

    Compose's autofill row, Cats' write-story badge and Ads' draft-copy button
    each built this — a status chip that moves thinking -> ready/warning/danger,
    with an Apply button that only appears once there is something to apply —
    independently before. This is the one component all three now share.
    """

    apply_requested = pyqtSignal()

    def __init__(self, thinking_text="Thinking…", parent=None):
        super().__init__(parent)
        # A gerund, not a bare verb: "Draft" -> "Drafting…" and "Rewrite" ->
        # "Rewriting…" don't share a suffix rule, so this takes the whole
        # word rather than guessing English conjugation from a verb stem.
        self._thinking_text = thinking_text
        self._payload = None
        # A real flag rather than "is the badge text still the thinking copy?" -
        # each tab's own thinking text differs ("Drafting…" vs "Rewriting…"),
        # so a caller (a test included) that waits for "no longer thinking"
        # needs a state check that doesn't depend on which copy was passed in.
        self.is_thinking = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        self.badge = Badge("", "neutral")
        self.badge.hide()
        self.apply_button = QPushButton("Apply")
        self.apply_button.setProperty("class", "primary")
        self.apply_button.hide()
        self.apply_button.clicked.connect(self._on_apply)
        layout.addWidget(self.badge)
        layout.addWidget(self.apply_button)
        layout.addStretch(1)

    def thinking(self, text=None):
        self.is_thinking = True
        self._payload = None
        self.apply_button.hide()
        self.badge.show()
        self.badge.set_status("accent", text or self._thinking_text)

    def ready(self, payload, text="Ready", status="success"):
        self.is_thinking = False
        self._payload = payload
        self.badge.show()
        self.badge.set_status(status, text)
        self.apply_button.show()

    def set_status(self, status, text):
        """Badge only - no payload change, no Apply button.

        For a caller with nothing to apply (Brief's Critique tab is a
        diagnosis, never a thing you "apply") but that still wants the same
        thinking/done visual language as the two tabs beside it that do.
        """
        self.is_thinking = False
        self.badge.show()
        self.badge.set_status(status, text)

    def warn(self, text):
        self.is_thinking = False
        self._payload = None
        self.badge.show()
        self.badge.set_status("warning", text)
        self.apply_button.hide()

    def fail(self, text):
        self.is_thinking = False
        self._payload = None
        self.badge.show()
        self.badge.set_status("danger", text)
        self.apply_button.hide()

    def reset(self):
        self.is_thinking = False
        self._payload = None
        self.badge.hide()
        self.apply_button.hide()

    def payload(self):
        return self._payload

    def _on_apply(self):
        if self._payload is not None:
            self.apply_requested.emit()


class GateTree(QWidget):
    """A lint/gate checklist: rows in a tree, the selected row's explanation in
    a label beneath it.

    `QTreeWidget` will not wrap text, so the checklists in cats.py, ads.py and
    sound.py each moved their prose into a label beside or below the tree
    independently. This is the one shared shape for that pattern, adopted by
    the Ads phase first (see the rebuild plan).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(T.SPACE["sm"])
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.itemSelectionChanged.connect(self._on_selection)
        self.detail = MutedLabel("")
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.detail)
        self._checks = []
        self._tokens = None

    def set_palette_tokens(self, tokens):
        self._tokens = tokens
        # Re-render with the new pass/fail colours rather than waiting for the
        # next set_checks() call, so a theme toggle repaints an open gate too.
        self.set_checks(self._checks)

    def set_checks(self, checks):
        """checks: list of {key, label, passed, fix, ok_text}, and optionally
        "state": "warn" - a row that PASSED but still has something to say.

        A warn row is amber and keeps passed=True, so all_passed() and every
        Generate button wired to it are unaffected. It exists because
        realism_lint's soft list ("8k", "masterpiece", "award-winning") only
        ever printed to the CLI: in the GUI those words rode along invisibly
        inside a green 8/8.
        """
        self._checks = list(checks)
        self.tree.clear()
        tokens = self._tokens or {}
        pick = lambda key: QColor(tokens[key]) if key in tokens else theme_color(key)  # noqa: E731
        ok_color, bad_color, warn_color = pick("success"), pick("error"), pick("warning")
        first_fail = None
        for check in self._checks:
            passed = bool(check.get("passed"))
            warned = passed and check.get("state") == "warn"
            mark = ("!  " if warned else "✓  ") if passed else "✕  "
            item = QTreeWidgetItem([mark + check.get("label", check.get("key", ""))])
            item.setData(0, Qt.ItemDataRole.UserRole, check)
            item.setForeground(0, (warn_color if warned else ok_color) if passed else bad_color)
            self.tree.addTopLevelItem(item)
            if not passed and first_fail is None:
                first_fail = item
        target = first_fail or (self.tree.topLevelItem(0) if self._checks else None)
        if target is not None:
            self.tree.setCurrentItem(target)
        else:
            self.detail.setText("")

    def _on_selection(self):
        items = self.tree.selectedItems()
        if not items:
            self.detail.setText("")
            return
        check = items[0].data(0, Qt.ItemDataRole.UserRole) or {}
        if check.get("passed"):
            # A warn row passed, but its `fix` is the whole point of showing
            # it - falling through to ok_text would say "no empty superlatives
            # found" on the row that just found some.
            if check.get("state") == "warn" and check.get("fix"):
                self.detail.setText(check["fix"])
            else:
                self.detail.setText(check.get("ok_text") or "")
        else:
            self.detail.setText(check.get("fix") or "")

    def all_passed(self):
        # `all([])` is True - an empty checklist must not read as a passing
        # gate (callers use this to enable a Generate button).
        return bool(self._checks) and all(c.get("passed") for c in self._checks)


def _swatch_icon(hex_color):
    """A small filled circle, for a chip that names a colour rather than a
    plain option - Hair/Eye colour need to show the colour, not just say it."""
    pixmap = QPixmap(12, 12)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(hex_color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, 12, 12)
    painter.end()
    return QIcon(pixmap)


class ChipButton(QPushButton):
    """A pill-shaped toggle. Age Range, Style & Aesthetic, Hair Color and Eye
    Color (Influencer Studio) all reuse this one class rather than four
    bespoke widgets - `swatch`, an optional hex colour, renders as a small
    dot before the label for the two colour pickers and is omitted for a
    plain text chip.
    """

    def __init__(self, key, label, swatch=None, parent=None):
        super().__init__(label, parent)
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("class", "chip")
        if swatch:
            self.setIcon(_swatch_icon(swatch))
            self.setIconSize(QSize(12, 12))


def chip_row(options, exclusive=False, columns=4):
    """Lay `options` - (key, label) or (key, label, swatch_hex) - into a
    wrapping QGridLayout of ChipButtons.

    Returns (layout, {key: ChipButton}, group_or_None). `group` is a real
    QButtonGroup when `exclusive` (Age Range, Hair Color, Eye Color - pick
    one), else None (Style & Aesthetic - toggle any number independently).
    The caller must keep a reference to the returned group (assign it to a
    `self.` attribute) - an unparented QButtonGroup with no surviving Python
    reference is a real "the exclusivity silently stopped working" bug.
    """
    layout = QGridLayout()
    layout.setHorizontalSpacing(T.SPACE["xs"])
    layout.setVerticalSpacing(T.SPACE["xs"])
    group = None
    if exclusive:
        group = QButtonGroup()
        group.setExclusive(True)
    buttons = {}
    for index, option in enumerate(options):
        key, label = option[0], option[1]
        swatch = option[2] if len(option) > 2 else None
        button = ChipButton(key, label, swatch)
        buttons[key] = button
        layout.addWidget(button, index // columns, index % columns)
        if group:
            group.addButton(button)
    return layout, buttons, group


class _EmptyHint(QObject):
    """Paints an icon and one line of guidance on an item view's viewport while
    the view holds no rows. See set_empty_hint()."""

    def __init__(self, view, text, icon_name):
        super().__init__(view)
        self.view = view
        self.text = text
        self.icon_name = icon_name

    def _empty(self):
        model = self.view.model()
        return model is None or model.rowCount() == 0

    def eventFilter(self, obj, event):
        # PyQt turns an exception escaping a virtual into a process abort, and at
        # shutdown the view can be gone before its viewport's last event: never
        # let a deleted-object RuntimeError out of here.
        if event.type() != QEvent.Type.Paint:
            return False
        try:
            empty = self._empty()
        except RuntimeError:
            return False
        if empty:
            painter = QPainter(obj)
            rect = obj.rect().adjusted(T.SPACE["md"], T.SPACE["sm"], -T.SPACE["md"], -T.SPACE["sm"])
            wrap = Qt.AlignmentFlag.AlignHCenter.value | Qt.TextFlag.TextWordWrap.value
            text_h = painter.fontMetrics().boundingRect(rect, wrap, self.text).height()
            # The icon only when icon + gap + the wrapped text all fit; a short
            # list (Compose's library is ~110px) gets the text alone, centred,
            # rather than a paragraph cut off at its bottom edge.
            size = 24
            gap = T.SPACE["sm"]
            if size + gap + text_h <= rect.height():
                top = rect.top() + (rect.height() - size - gap - text_h) // 2
                assets.icon(self.icon_name).paint(painter, rect.center().x() - size // 2, top, size, size)
                rect.setTop(top + size + gap)
                vertical = Qt.AlignmentFlag.AlignTop
            else:
                vertical = Qt.AlignmentFlag.AlignVCenter
            painter.setPen(theme_color("text_muted"))
            painter.drawText(rect, wrap | vertical.value, self.text)
            painter.end()
        return False


def set_empty_hint(view, text, icon_name="images"):
    """An empty list or table says what goes there and how to fill it, instead
    of showing a blank box ("Save a character to see it here"). Repaints on
    every row change, and costs nothing once the view has rows."""
    hint = _EmptyHint(view, text, icon_name)
    view.viewport().installEventFilter(hint)

    def repaint(*_):
        try:
            view.viewport().update()
        except RuntimeError:           # the view is already deleted (app shutdown)
            pass
    model = view.model()
    if model is not None:
        for signal in (model.rowsInserted, model.rowsRemoved, model.modelReset):
            signal.connect(repaint)
    view._empty_hint = hint
    return hint


def _layout_path(layout, widget):
    """The flat, in-order list of widgets of the (nested) layout holding `widget`,
    or None when `widget` is not in it."""
    flat, found = [], False
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            flat.append(item.widget())
            found = found or item.widget() is widget
        elif item.layout() is not None:
            inner = _layout_path(item.layout(), widget)
            if inner is not None:
                return inner
    return flat if found else None


def _first_sentence(text, limit=60):
    text = " ".join((text or "").split())
    for stop in (". ", " - ", "; "):
        if stop in text:
            text = text.split(stop, 1)[0]
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def name_controls(root):
    """Give every unnamed input, combo, text box and icon-only button under
    `root` an accessible name, from what a sighted user reads beside it:
    the short label just before it in its layout (also set as its buddy),
    else its tooltip's first sentence, else its placeholder, else the title
    of the card it sits in. A screen reader otherwise announced 125 of them
    as just "combo box" / "edit". Never overrides a name a view set itself.
    Returns how many it named."""
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QComboBox, QFormLayout,
                                 QLineEdit, QPlainTextEdit, QTextEdit)
    named = set()
    for form in root.findChildren(QFormLayout):     # a form row's label already names its field
        for row in range(form.rowCount()):
            label = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label and field and isinstance(label.widget(), QLabel) and field.widget() is not None:
                if not field.widget().accessibleName():
                    field.widget().setAccessibleName(label.widget().text().rstrip(":"))
                named.add(id(field.widget()))
    count = 0
    kinds = (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit)
    for widget in root.findChildren(kinds):
        if widget.accessibleName() or id(widget) in named:
            continue
        if isinstance(widget, QAbstractButton) and widget.text().strip():
            continue                                    # its own text names it
        if isinstance(widget.parentWidget(), (QComboBox, QAbstractSpinBox)):
            continue                                    # a combo / spin box's inner editor
        name = ""
        parent = widget.parentWidget()
        siblings = _layout_path(parent.layout(), widget) if parent is not None and parent.layout() else None
        if siblings:
            before = siblings[:siblings.index(widget)]
            for prior in reversed(before[-2:]):
                if isinstance(prior, QLabel) and 0 < len(prior.text().strip()) <= 40 and prior.buddy() is None:
                    name = prior.text().strip().rstrip(":")
                    prior.setBuddy(widget)
                    break
        if not name:
            name = _first_sentence(widget.toolTip())
        if not name:
            # The card's title before the placeholder: a placeholder is usually
            # an EXAMPLE value ("a tired barista closing up late"), not a name.
            node = parent
            while node is not None and not name:
                title = node.findChild(TitleLabel)
                if title is not None and title.text():
                    name = title.text()
                node = node.parentWidget()
        if not name and isinstance(widget, (QLineEdit, QPlainTextEdit)):
            name = _first_sentence(widget.placeholderText())
        if name:
            widget.setAccessibleName(name)
            if widget.toolTip() and not widget.accessibleDescription():
                widget.setAccessibleDescription(" ".join(widget.toolTip().split()))
            count += 1
    return count


def short_paths(text):
    """`text` with every absolute local path shown as just its file name
    ("C:\\Users\\<you>\\...\\AI Video Studio\\.env" -> ".env"). For messages from
    tools/ shown inside the window: the full path helps on a command line, but
    in the GUI it is noise - and it puts the user's name in every screenshot."""
    import re
    text = re.sub(r"[A-Za-z]:\\(?:[^\\\n]+\\)*([^\\\s]+)", r"\1", text or "")
    return re.sub(r"(?<![\w.:/])/(?:[^/\s]+/)+([^/\s]+)", r"\1", text)


def status_line(text, limit=160):
    """One readable status-bar line from any message: its first line, a local
    path shown as just its file name, a URL as just its site, at most `limit`
    characters. The status bar is glanced at, not read - a full
    "C:\\Users\\...\\AI Video Studio\\.env" and a deep link pushed the part that
    mattered off the edge. The caller keeps the full text for the tooltip."""
    import re
    lines = [line for line in (text or "").strip().splitlines() if line.strip()]
    if not lines:
        return ""
    line = lines[0].strip()
    line = re.sub(r"https?://(?:www\.)?([^/\s]+)\S*", r"\1", line)
    # Windows folders may hold spaces ("Personal Projects"); the last part may not.
    line = short_paths(line)
    return line if len(line) <= limit else line[:limit - 1].rstrip() + "…"


def readable_tabs(root):
    """Every tab bar under `root` shows whole labels: no "Purp..." elision, and
    a bar too narrow for its tabs gets scroll arrows instead. Elision hid what
    a tab WAS - in Compose's narrow spec column all five read as fragments."""
    from PyQt6.QtWidgets import QTabBar
    for bar in root.findChildren(QTabBar):
        bar.setElideMode(Qt.TextElideMode.ElideNone)
        bar.setUsesScrollButtons(True)
        bar.setDocumentMode(False)
        for i in range(bar.count()):           # the full name on hover, also read by screen readers
            if not bar.tabToolTip(i):
                bar.setTabToolTip(i, bar.tabText(i).replace("&", ""))


def mark_error(widget, is_error):
    """Toggle the `hasError` input state the QSS defines."""
    if bool(widget.property("hasError")) == bool(is_error):
        return
    widget.setProperty("hasError", "true" if is_error else "false")
    repolish(widget)


def divider(horizontal=True):
    line = QFrame()
    line.setProperty("class", "divider")
    line.setFixedHeight(1) if horizontal else line.setFixedWidth(1)
    return line
