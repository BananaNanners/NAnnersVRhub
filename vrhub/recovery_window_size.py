# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Explicit recovery window sizes; percentages refer to available screen area."""
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox

DEFAULT_PERCENT = 80
PRESETS = (70, 80, 90)


class RecoveryWindowSize(QWidget):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel('Window size:'))
        self.selector = QComboBox()
        for percent in PRESETS:
            self.selector.addItem(f'{percent}%', percent)
        self.selector.addItem('Custom', None)
        self.selector.setToolTip('Resize this window relative to available screen width and height. This does not change text or desktop scaling. Custom follows manual resizing.')
        row.addWidget(self.selector)
        self.readout = QLabel()
        row.addWidget(self.readout)
        row.addStretch(1)
        self.selector.currentIndexChanged.connect(self.apply_preset)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.update_readout)
        dialog.installEventFilter(self)
        self.update_readout()

    def eventFilter(self, watched, event):
        if event.type() in {QEvent.Resize, QEvent.Move, QEvent.Show, QEvent.WindowStateChange}:
            self._timer.start(0)
        return super().eventFilter(watched, event)

    def apply_preset(self, index):
        percent = self.selector.itemData(index)
        if percent not in PRESETS:
            return
        screen = self.dialog.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        if self.dialog.isMaximized() or self.dialog.isFullScreen():
            self.dialog.showNormal()
        self.dialog.resize(max(1, int(available.width() * percent / 100)),
                           max(1, int(available.height() * percent / 100)))
        self._timer.start(0)

    def update_readout(self):
        screen = self.dialog.screen()
        if screen is None:
            self.readout.setText('Actual size unavailable')
            return
        available = screen.availableGeometry()
        if available.width() <= 0 or available.height() <= 0:
            self.readout.setText('Actual size unavailable')
            return
        width, height = self.dialog.width(), self.dialog.height()
        wide, high = width * 100 / available.width(), height * 100 / available.height()
        self.readout.setText(f'Actual: {wide:.0f}% wide × {high:.0f}% high')
        self.readout.setToolTip(f'Window content: {width} × {height} logical pixels\n'
                               f'Available screen: {available.width()} × {available.height()} logical pixels\n'
                               f'Qt pixel scale: {self.dialog.devicePixelRatioF() * 100:.0f}%\n'
                               'Percentages exclude window borders/title bar and do not change desktop scaling.')
        matched = next((p for p in PRESETS
                        if abs(width - int(available.width() * p / 100)) <= 1
                        and abs(height - int(available.height() * p / 100)) <= 1), None)
        blocked = self.selector.blockSignals(True)
        self.selector.setCurrentIndex(self.selector.findData(matched))
        self.selector.blockSignals(blocked)
