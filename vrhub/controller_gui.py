"""Searchable, read-only Quest controller references for the Games page."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget
from . import controller_bindings as bindings


class ControllerDiagram(QWidget):
    """Neutral button-location key, drawn locally at any display scale."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(166)
        self.setMaximumHeight(186)
        self.setAccessibleName('Quest controller button locations')
        self.setAccessibleDescription('Left: X lower, Y upper, menu, L3 stick click. Right: A lower, B upper, Meta system, R3 stick click. Index triggers are at the front; grip triggers are on the side. Meta system is reserved for the headset.')
        self.setToolTip('Button location key; game actions appear in the table below. L3/R3 = press the thumbstick.')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min(self.width() / 680, self.height() / 174)
        p.translate((self.width() - 680 * scale) / 2, (self.height() - 174 * scale) / 2)
        p.scale(scale, scale)
        p.setFont(QFont('Sans Serif', 10))
        for x, left in [(0, True), (350, False)]:
            accent = QColor('#23B7FF' if left else '#FFD21A')
            p.setPen(QPen(accent, 1.5))
            p.setBrush(QColor('#171D23'))
            p.drawRoundedRect(QRectF(x + 105, 26, 115, 90), 30, 30)
            p.drawRoundedRect(QRectF(x + 125, 100, 56, 61), 17, 17)
            p.drawText(QRectF(x + 80, 0, 160, 22), Qt.AlignCenter, 'LEFT HAND' if left else 'RIGHT HAND')
            # Stick is outside; face buttons are inside in the top-face view.
            sx = x + (129 if left else 195)
            bx = x + (188 if left else 137)
            p.drawEllipse(QRectF(sx - 15, 49, 30, 30))
            p.drawText(QRectF(sx - 18, 53, 36, 22), Qt.AlignCenter, 'L3' if left else 'R3')
            for y, label in [(52, 'Y' if left else 'B'), (82, 'X' if left else 'A')]:
                p.drawEllipse(QRectF(bx - 11, y - 11, 22, 22))
                p.drawText(QRectF(bx - 11, y - 11, 22, 22), Qt.AlignCenter, label)
            p.setPen(QColor('#F5F2DE'))
            p.drawText(QRectF(x, 26, 100, 20), Qt.AlignRight, 'Index trigger')
            p.drawLine(x + 101, 37, x + 146, 30)
            p.drawText(QRectF(x, 116, 100, 20), Qt.AlignRight, 'Grip trigger')
            p.drawLine(x + 102, 126, x + 126, 128)
            p.setFont(QFont('Sans Serif', 9))
            p.drawText(QRectF(x + 222, 90, 106, 52), Qt.AlignLeft | Qt.TextWordWrap,
                       'Menu button' if left else 'Meta / system\nHeadset reserved')
            p.drawLine(x + 203, 101, x + 220, 102)
            p.setFont(QFont('Sans Serif', 10))
        p.end()


class ControllerBindingsPage(QWidget):
    def __init__(self, parent=None, *, allow_expand=True):
        super().__init__(parent)
        self.guide = None
        self.recipe_id = None
        self.expanded = None
        layout = QVBoxLayout(self)
        self.diagram = ControllerDiagram()
        layout.addWidget(self.diagram)
        key = QLabel('Quest / Touch layout  •  L3 / R3 = thumbstick clicks  •  Keyboard shortcuts are labelled separately')
        key.setWordWrap(True)
        key.setStyleSheet('color: #A7ADB7;')
        layout.addWidget(key)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find a control: rotate, PDA, grip, spell…')
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('Search controller bindings')
        self.category = QComboBox()
        self.category.setAccessibleName('Controller binding section')
        self.copy_button = QPushButton('Copy full guide')
        self.copy_button.setToolTip('Copy all sections, evidence labels, notes and sources, including hidden search results.')
        layout.addWidget(self.search)
        row.addWidget(self.category, 1)
        row.addWidget(self.copy_button)
        self.expand_button = QPushButton('Expand…')
        self.expand_button.setToolTip('Open this game’s reference in a larger window.')
        self.expand_button.setVisible(allow_expand)
        self.expand_button.clicked.connect(self.expand_guide)
        row.addWidget(self.expand_button)
        layout.addLayout(row)
        self.results = QTextBrowser()
        self.results.setOpenExternalLinks(True)
        self.results.setAccessibleName('Controller bindings guide')
        layout.addWidget(self.results, 1)
        self.count = QLabel()
        self.count.setStyleSheet('color: #A7ADB7;')
        layout.addWidget(self.count)
        self.search.textChanged.connect(self.render)
        self.category.currentTextChanged.connect(self.render)
        self.copy_button.clicked.connect(self.copy_guide)
        self.set_recipe(None)

    def set_recipe(self, recipe):
        rid = recipe.get('id') if recipe else None
        if rid == self.recipe_id and self.guide is not None:
            return
        self.recipe_id = rid
        self.guide = None
        self.search.blockSignals(True)
        self.category.blockSignals(True)
        self.search.clear()
        self.category.clear()
        self.category.addItem('All sections')
        error = None
        try:
            if rid:
                self.guide = bindings.load(rid)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            error = f'Controller guide unavailable: {exc}'
        if self.guide:
            self.category.addItems([s['name'] for s in self.guide['sections']])
        self.search.blockSignals(False)
        self.category.blockSignals(False)
        for widget in (self.search, self.category, self.copy_button, self.expand_button):
            widget.setEnabled(self.guide is not None)
        if error:
            self.results.setPlainText(error)
            self.count.setText('Guide unavailable')
        else:
            self.render()

    def render(self, *_):
        if self.guide is None:
            self.results.setPlainText('Select a game to see its controller reference.' if not self.recipe_id else 'No controller guide is bundled for this game yet.')
            self.count.clear()
            return
        query, category = self.search.text(), self.category.currentText()
        self.results.setHtml(bindings.html(self.guide, query, category))
        shown = sum(len(s['bindings']) for s in bindings.filtered_sections(self.guide, query, category))
        total = sum(len(s['bindings']) for s in self.guide['sections'])
        self.count.setText(f'{shown} of {total} controls  •  Reference guide; custom mappings may differ')

    def copy_guide(self):
        if self.guide:
            QApplication.clipboard().setText(bindings.plain_text(self.guide))
            self.count.setText('Full guide copied, including notes and sources.')

    def expand_guide(self):
        if not self.guide:
            return
        if self.expanded is not None:
            self.expanded.close()
        dialog = QDialog(self)
        dialog.setObjectName('controllerBindingsDialog')
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setWindowTitle('Controller bindings — ' + self.guide['title'])
        dialog.resize(980, 800)
        page = ControllerBindingsPage(dialog, allow_expand=False)
        page.set_recipe({'id': self.recipe_id})
        page.category.setCurrentText(self.category.currentText())
        page.search.setText(self.search.text())
        layout = QVBoxLayout(dialog)
        layout.addWidget(page)
        self.expanded = dialog
        dialog.finished.connect(lambda _: setattr(self, 'expanded', None))
        dialog.show()
