"""
Switch — a macOS-style toggle switch widget for Kairo.

QAbstractButton subclass, so it comes with the standard clicked /
toggled(bool) / pressed signals and setCheckable() behavior. Paints a
13px label on the left and a green/gray pill switch on the right
(the classic macOS "System Settings" toggle), so it reads as a single
control:  "Focus Assist  (pill)".
"""
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QFontMetrics, QPainter, QPen


class Switch(QtWidgets.QAbstractButton):
    """A labeled macOS-style toggle switch (green when ON)."""

    PILL_W = 38
    PILL_H = 22
    PAD = 10          # gap between label and pill
    MARGIN_R = 4

    def __init__(self, label="On", parent=None):
        super(Switch, self).__init__(parent)
        self._label_text = label
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(self._size())

    def _size(self):
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self._label_text)
        w = text_w + self.PAD + self.PILL_W + self.MARGIN_R
        return QtCore.QSize(w, max(self.PILL_H + 6, 26))

    def sizeHint(self):
        return self._size()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        on = self.isChecked()

        # Label
        color = QColor("#f5f5f7") if on else QColor("#a1a1a6")
        p.setPen(color)
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self._label_text)
        p.drawText(QRectF(0, 0, text_w, h),
                   Qt.AlignVCenter | Qt.AlignLeft, self._label_text)

        # Pill
        pill = QRectF(self.width() - self.PILL_W - self.MARGIN_R,
                      (h - self.PILL_H) / 2, self.PILL_W, self.PILL_H)
        r = self.PILL_H / 2
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#30d158"))
            p.drawRoundedRect(pill, r, r)
        else:
            p.setPen(QPen(QColor("#48484a"), 1))
            p.setBrush(QColor("#39393d"))
            p.drawRoundedRect(pill.adjusted(0.5, 0.5, -0.5, -0.5), r, r)

        # Knob
        d = self.PILL_H - 4
        knob_x = (pill.left() + pill.width() - d - 2) if on else (pill.left() + 2)
        knob = QRectF(knob_x, pill.top() + 2, d, d)
        p.setPen(QPen(QColor("#000000"), 0.5))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(knob)
        p.end()
