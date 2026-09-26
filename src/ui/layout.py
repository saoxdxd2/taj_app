"""Layout-safety helpers.

Prevents the two classic interface defects:

1. Overlapping widgets when a fixed pixel size is wrong.
2. Text spilling out of a button or being clipped when the label is
   longer than expected.

The root cause of both is hardcoded geometry. A 44px sidebar looks fine
at 100% DPI with English text, then overlaps at 150% DPI or once the
label is translated to French (typically ~20% longer than English).

Everything here is therefore expressed in *font metrics* or layout
policy, never in absolute pixels:

- `scaled(px)` converts a design-time pixel value into the current
  device's logical pixels, so a size chosen for a 96 DPI reference
  screen stays proportional at 125%/150% scaling.
- `text_width(widget, text)` measures real rendered text, so a control
  can be sized to its content instead of guessed.
- `elided(text, widget)` shortens text with an ellipsis rather than
  letting it overflow.
- `autosize_button` / `autosize_label` apply that sizing to widgets.
- `add_elided_columns(table, ...)` makes table cells degrade gracefully
  instead of forcing the user to scroll horizontally.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QAbstractButton, QHeaderView, QLabel, QSizePolicy, QTableWidget,
)

# Reference DPI for the values in the stylesheet. Qt's logical pixels are
# defined at 96 DPI, so dividing by the device ratio converts a design
# measurement into current logical pixels.
REFERENCE_DPI = 96.0


def device_pixel_ratio() -> float:
    """
    Returns the current device pixel ratio (1.0 at 100% scaling).

    Read from the primary screen, so it is correct before any window
    exists. Falls back to 1.0 if no screen is available (headless).
    """
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return 1.0
    return screen.devicePixelRatio() or 1.0


def scaled(pixels: float) -> int:
    """
    Converts a design-time pixel measurement to the current display.

    Use this for padding, icon sizes and minimum heights so the interface
    keeps its proportions on a high-DPI screen instead of shrinking into
    unreadable, overlapping clutter.
    """
    return max(1, int(round(pixels * device_pixel_ratio())))


def font_metrics(widget=None) -> QFontMetrics:
    """Returns metrics for the widget's font, or the app's default font."""
    if widget is not None:
        return QFontMetrics(widget.font())
    app = QApplication.instance()
    if app is None:
        return QFontMetrics(QGuiApplication.font())
    return QFontMetrics(app.font())


def text_width(text: str, widget=None) -> int:
    """Width in logical pixels that `text` actually needs when rendered."""
    return font_metrics(widget).horizontalAdvance(text or "")


def text_height(text: str, widget=None) -> int:
    """Height in logical pixels that `text` actually needs."""
    return font_metrics(widget).height()


def elided(text: str, available_width: int, widget=None) -> str:
    """
    Shortens `text` with an ellipsis so it fits `available_width`.

    Returns the text unchanged when it already fits, so short labels are
    never mangled.
    """
    metrics = font_metrics(widget)
    return metrics.elidedText(text or "", Qt.ElideRight, max(0, available_width))


def autosize_button(button: QAbstractButton, extra_padding: int = 0) -> None:
    """
    Sizes a button to its own text, with a minimum, and lets it grow.

    Fixes "text out of the button": the width is derived from the real
    font metrics of the current label (which changes with translation),
    and the size policy allows expansion rather than clipping.
    """
    metrics = font_metrics(button)
    padding = scaled(24) + extra_padding
    width = metrics.horizontalAdvance(button.text()) + padding
    button.setMinimumWidth(width)
    # Expanding horizontally keeps a translated (longer) label readable.
    button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)


def autosize_label(label: QLabel, max_lines: int = 1) -> None:
    """
    Lets a label wrap instead of forcing a fixed pixel box.

    A QLabel with a fixed height clips its text as soon as the string
    grows; word wrap plus an expanding size policy removes that failure
    mode entirely.
    """
    label.setWordWrap(True)
    label.setMinimumHeight(text_height("Ag", label) * max_lines)
    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


def autosize_dialog(dialog, min_width: int = 440) -> None:
    """
    Gives a dialog a DPI-scaled minimum width and a sensible default.

    Replaces `setFixedWidth`, which pinned the dialog to a pixel value
    that is wrong on any other display and clips translated labels.
    """
    dialog.setMinimumWidth(scaled(min_width))
    dialog.setSizeGripEnabled(True)


def add_elided_columns(table: QTableWidget, stretch_column: int = 0) -> None:
    """
    Makes a table degrade gracefully instead of overflowing.

    The previous pattern was Stretch on every column, which is the actual
    cause of the "text is cut off" defect: one long value squeezes all the
    other columns to their minimum instead of simply being elided.

    Here every column sizes to its content, the designated column absorbs
    the leftover space, and any cell that still does not fit is elided
    with '...' rather than clipped mid-word.
    """
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for index in range(table.columnCount()):
        if index == stretch_column:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideRight)


def size_table_height(table, visible_rows: int = 8) -> None:
    """
    Caps a table at a row count instead of a pixel height.

    A fixed pixel height (setMaximumHeight(160)) shows a half row and
    clips the rest, and it does not scale with the DPI or the font. This
    sizes the viewport to whole rows, which always looks intentional.
    """
    header = table.horizontalHeader()
    row_height = table.rowHeight(0) if table.rowCount() else scaled(24)
    # +1 so the header itself remains visible.
    table.setMaximumHeight(
        header.height() + row_height * visible_rows + scaled(8)
    )
