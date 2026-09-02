"""Main application window."""

import logging

from PyQt5.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QRectF,
    Qt,
    QThread,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import (
    DEFAULT_INSTRUMENT_IP,
    POLL_INTERVAL_MS,
    READOUT_DECIMALS,
    SETPOINT_DECIMALS,
    SETPOINT_DEFAULT,
    SETPOINT_MAX,
    SETPOINT_MIN,
    SETPOINT_STEP_DEFAULT,
    SETPOINT_TOLERANCE_BAR,
    SLEW_DECIMALS,
    SLEW_DEFAULT,
    SLEW_MAX,
    SLEW_MIN,
    UNIT_PRESSURE,
    UNIT_RATE,
    WINDOW_GEOMETRY,
    WINDOW_TITLE,
)
from .instrument import ControlMode, InstrumentError, PressureInstrument

logger = logging.getLogger(__name__)


class ImmediateSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that emits editingFinished right after an arrow-button step.

    QAbstractSpinBox's editingFinished only fires on Enter or focus loss, so
    without this, clicking the step arrows wouldn't push the new value to
    the instrument until the user tabbed away.
    """

    def stepBy(self, steps: int) -> None:
        super().stepBy(steps)
        self.editingFinished.emit()


class SteppedSpinBox(ImmediateSpinBox):
    """ImmediateSpinBox whose arrow step is driven by an external step spinbox."""

    def __init__(self, step_source: QDoubleSpinBox, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step_source = step_source

    def stepBy(self, steps: int) -> None:
        step = self._step_source.value()
        self.setValue(self.value() + steps * step)
        self.editingFinished.emit()


class ModeSwitch(QWidget):
    """A fat pill-shaped switch between MEASURE (left) and CONTROL (right).

    The thumb sits over whichever side is currently active, so the label
    it covers is the current state and the label it's not covering is
    what a click will switch to.
    """

    MEASURE_COLOR = QColor("#4a90d9")
    CONTROL_COLOR = QColor("#e07b39")
    TRACK_COLOR = QColor("#dce3e8")
    DISABLED_COLOR = QColor("#aaaaaa")

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = False
        self._offset = 0.0  # 0.0 = MEASURE (left), 1.0 = CONTROL (right)
        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True) -> None:
        self._checked = checked
        target = 1.0 if checked else 0.0
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._offset)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.offset = target

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = pyqtProperty(float, _get_offset, _set_offset)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self.isEnabled() and event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            self.clicked.emit()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        radius = rect.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.TRACK_COLOR if self.isEnabled() else self.DISABLED_COLOR)
        painter.drawRoundedRect(rect, radius, radius)

        thumb_width = rect.width() / 2
        thumb_rect = QRectF(
            rect.x() + self._offset * (rect.width() - thumb_width),
            rect.y(),
            thumb_width,
            rect.height(),
        )
        thumb_color = self.CONTROL_COLOR if self._checked else self.MEASURE_COLOR
        painter.setBrush(thumb_color if self.isEnabled() else self.DISABLED_COLOR)
        painter.drawRoundedRect(thumb_rect, radius, radius)

        font = QFont(self.font())
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)

        left_rect = QRectF(rect.x(), rect.y(), thumb_width, rect.height())
        right_rect = QRectF(rect.x() + thumb_width, rect.y(), thumb_width, rect.height())

        active_text = QColor("white")
        inactive_text = QColor("#607d8b") if self.isEnabled() else QColor("#888888")

        painter.setPen(inactive_text if self._checked else active_text)
        painter.drawText(left_rect, Qt.AlignCenter, "MEASURE")
        painter.setPen(active_text if self._checked else inactive_text)
        painter.drawText(right_rect, Qt.AlignCenter, "CONTROL")


class PollWorker(QObject):
    """Polls the instrument on a background thread.

    Each poll does three blocking VISA round-trips; running them on the GUI
    thread froze all UI event processing (hover highlights, repaints, ...)
    for that duration. The timer is created inside start() so it's driven by
    this worker's own thread's event loop once moved there.
    """

    reading = pyqtSignal(float, float, float)
    poll_error = pyqtSignal(str)

    def __init__(self, instrument: PressureInstrument, interval_ms: int) -> None:
        super().__init__()
        self._instrument = instrument
        self._interval_ms = interval_ms
        self._timer: QTimer | None = None

    def start(self) -> None:
        if self._timer is None:
            self._timer = QTimer()
            self._timer.setInterval(self._interval_ms)
            self._timer.timeout.connect(self._poll)
            # Stop the timer from its own thread as that thread shuts down,
            # so Qt never has to kill it from the main thread during cleanup.
            self.thread().finished.connect(self._timer.stop)
        self._timer.start()

    def _poll(self) -> None:
        try:
            pressure = self._instrument.read_pressure()
            rate = self._instrument.read_rate()
            source = self._instrument.read_source_pressure()
        except InstrumentError as exc:
            self.poll_error.emit(str(exc))
            return
        self.reading.emit(pressure, rate, source)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(*WINDOW_GEOMETRY)

        self._instrument = PressureInstrument()

        self._poll_thread = QThread(self)
        self._poll_worker = PollWorker(self._instrument, POLL_INTERVAL_MS)
        self._poll_worker.moveToThread(self._poll_thread)
        self._poll_thread.started.connect(self._poll_worker.start)
        self._poll_worker.reading.connect(self._on_reading)
        self._poll_worker.poll_error.connect(self._on_poll_error)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setSpacing(12)

        self._step_input = self._build_step_input()

        root.addLayout(self._build_connection_row())
        root.addWidget(self._build_mode_switch())

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.addWidget(self._build_pressure_card())
        cards_row.addWidget(self._build_slew_card())
        root.addLayout(cards_row)

        root.addLayout(self._build_secondary_row())

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def _build_connection_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect)

        self._connection_status = QLabel("Status: Disconnected")

        layout.addWidget(self._connect_btn)
        layout.addWidget(self._connection_status)
        layout.addStretch()
        return layout

    def _build_mode_switch(self) -> ModeSwitch:
        self._mode_switch = ModeSwitch()
        self._mode_switch.setEnabled(False)
        self._mode_switch.clicked.connect(self._on_toggle_mode)
        return self._mode_switch

    def _build_step_input(self) -> QDoubleSpinBox:
        step_input = QDoubleSpinBox()
        step_input.setDecimals(SETPOINT_DECIMALS)
        step_input.setRange(0.0001, SETPOINT_MAX)
        step_input.setValue(SETPOINT_STEP_DEFAULT)
        step_input.setEnabled(False)
        return step_input

    def _build_pressure_card(self) -> QFrame:
        self._setpoint_input = SteppedSpinBox(step_source=self._step_input)
        self._setpoint_input.setDecimals(SETPOINT_DECIMALS)
        self._setpoint_input.setRange(SETPOINT_MIN, SETPOINT_MAX)
        self._setpoint_input.setValue(SETPOINT_DEFAULT)
        self._setpoint_input.setEnabled(False)
        self._setpoint_input.editingFinished.connect(self._on_send_setpoint)

        return self._build_pair_card(
            title="Pressure",
            left_title="Setpoint",
            left_widget=self._setpoint_input,
            right_title="Current",
            right_attr="_pressure_label",
            unit=UNIT_PRESSURE,
        )

    def _build_slew_card(self) -> QFrame:
        self._slew_input = ImmediateSpinBox()
        self._slew_input.setDecimals(SLEW_DECIMALS)
        self._slew_input.setRange(SLEW_MIN, SLEW_MAX)
        self._slew_input.setValue(SLEW_DEFAULT)
        self._slew_input.setEnabled(False)
        self._slew_input.editingFinished.connect(self._on_send_slew)

        return self._build_pair_card(
            title="Slew Rate",
            left_title="Aim",
            left_widget=self._slew_input,
            right_title="Current",
            right_attr="_rate_label",
            unit=UNIT_RATE,
        )

    def _build_pair_card(
        self,
        title: str,
        left_title: str,
        left_widget: QDoubleSpinBox,
        right_title: str,
        right_attr: str,
        unit: str,
    ) -> QFrame:
        """A card pairing an editable target value with its live readout, at equal visual weight."""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Sunken)

        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)

        sub_font = QFont()
        sub_font.setPointSize(10)

        big_font = QFont()
        big_font.setPointSize(22)
        big_font.setBold(True)

        outer = QVBoxLayout(frame)
        outer.setSpacing(8)

        header = QLabel(title)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)
        outer.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setAlignment(Qt.AlignCenter)
        left_lbl = QLabel(left_title)
        left_lbl.setFont(sub_font)
        left_lbl.setAlignment(Qt.AlignCenter)
        left_widget.setFont(big_font)
        left_widget.setAlignment(Qt.AlignCenter)
        left_col.addWidget(left_lbl)
        left_col.addWidget(left_widget)
        row.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignCenter)
        right_lbl = QLabel(right_title)
        right_lbl.setFont(sub_font)
        right_lbl.setAlignment(Qt.AlignCenter)
        value_lbl = QLabel("—")
        value_lbl.setFont(big_font)
        value_lbl.setAlignment(Qt.AlignCenter)
        # Fixed width (sized for the worst-case digit count) so the card
        # doesn't reflow as the reading's magnitude/sign changes.
        value_lbl.setFixedWidth(QFontMetrics(big_font).horizontalAdvance("-1000.000"))
        setattr(self, right_attr, value_lbl)
        right_col.addWidget(right_lbl)
        right_col.addWidget(value_lbl)
        row.addLayout(right_col)

        outer.addLayout(row)

        unit_lbl = QLabel(unit)
        unit_lbl.setFont(sub_font)
        unit_lbl.setAlignment(Qt.AlignCenter)
        outer.addWidget(unit_lbl)

        return frame

    def _build_secondary_row(self) -> QHBoxLayout:
        """Lower-emphasis controls: source pressure readout and the setpoint step size."""
        layout = QHBoxLayout()
        layout.setSpacing(24)

        sub_font = QFont()
        sub_font.setPointSize(10)

        step_title = QLabel("Setpoint Step:")
        step_title.setFont(sub_font)
        step_unit = QLabel(UNIT_PRESSURE)
        step_unit.setFont(sub_font)

        layout.addWidget(step_title)
        layout.addWidget(self._step_input)
        layout.addWidget(step_unit)

        layout.addStretch()

        src_title = QLabel("Source Pressure:")
        src_title.setFont(sub_font)
        self._source_pressure_label = QLabel("—")
        self._source_pressure_label.setFont(sub_font)
        self._source_pressure_label.setAlignment(Qt.AlignCenter)
        self._source_pressure_label.setFixedWidth(
            QFontMetrics(sub_font).horizontalAdvance("-1000.000")
        )
        src_unit = QLabel(UNIT_PRESSURE)
        src_unit.setFont(sub_font)

        layout.addWidget(src_title)
        layout.addWidget(self._source_pressure_label)
        layout.addWidget(src_unit)

        return layout

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_connect(self) -> None:
        if self._instrument.is_connected:
            self._set_connected_state(False)
            self._instrument.disconnect()
            return

        try:
            address = self._resolve_address()
            if address is None:
                return

            self._instrument.connect(address)
            self._set_connected_state(True)
            # Read initial mode from instrument
            try:
                mode = self._instrument.read_mode()
                self._apply_mode_ui(mode)
            except InstrumentError as exc:
                logger.warning("Could not read initial mode: %s", exc)
            self._connection_status.setText("Status: Connected")
        except InstrumentError as exc:
            logger.error("Connection failed: %s", exc)
            QMessageBox.critical(self, "Connection Error", str(exc))

    def _resolve_address(self) -> str | None:
        """Pick the VISA address to connect to: an auto-recognized instrument,
        a user's pick among discovered candidates, or — if nothing answers
        discovery, as is common for static-IP Ethernet instruments — a
        manually entered IP address.
        """
        recognized = self._instrument.find_recognized_resources()
        if len(recognized) == 1:
            return recognized[0]

        selectable = recognized or self._instrument.list_candidate_resources()

        if not selectable:
            return self._prompt_manual_address()

        title = "Select Inflator"
        label = (
            "Select the detected inflator:"
            if recognized
            else "No device was recognized automatically. Select a device:"
        )
        address, ok = QInputDialog.getItem(self, title, label, selectable, 0, False)
        return address if ok and address else None

    def _prompt_manual_address(self) -> str | None:
        """Ask for an instrument IP address directly, for Ethernet instruments
        that don't respond to VISA's discovery broadcast.
        """
        ip, ok = QInputDialog.getText(
            self,
            "Connect by IP",
            "No USB or Ethernet device found automatically.\n"
            "Enter the instrument's IP address:",
            text=DEFAULT_INSTRUMENT_IP,
        )
        if not ok or not ip.strip():
            return None
        return f"TCPIP::{ip.strip()}::INSTR"

    def _on_toggle_mode(self) -> None:
        # Switch already flipped itself on click: checked = CONTROL, unchecked = MEASURE
        want_control = self._mode_switch.isChecked()
        try:
            if want_control:
                self._instrument.set_control(self._setpoint_input.value())
            else:
                self._instrument.set_measure()
            mode = ControlMode.CONTROL if want_control else ControlMode.MEASURE
            self._apply_mode_ui(mode)
        except InstrumentError as exc:
            logger.error("Mode switch failed: %s", exc)
            QMessageBox.critical(self, "Mode Error", str(exc))
            # Revert switch state
            self._mode_switch.setChecked(not want_control)

    def _apply_mode_ui(self, mode: ControlMode) -> None:
        is_control = mode is ControlMode.CONTROL
        self._mode_switch.setChecked(is_control)
        if not is_control:
            self._pressure_label.setStyleSheet("")

    def _on_reading(self, pressure: float, rate: float, source: float) -> None:
        self._pressure_label.setText(f"{pressure:.{READOUT_DECIMALS}f}")
        self._rate_label.setText(f"{rate:.{READOUT_DECIMALS}f}")
        self._source_pressure_label.setText(f"{source:.{READOUT_DECIMALS}f}")
        self._update_pressure_color(pressure)

    def _on_poll_error(self, message: str) -> None:
        logger.warning("Poll failed: %s", message)

    def _on_send_setpoint(self) -> None:
        try:
            self._instrument.set_pressure(self._setpoint_input.value())
        except InstrumentError as exc:
            logger.error("Set pressure failed: %s", exc)
            QMessageBox.critical(self, "Write Error", str(exc))

    def _on_send_slew(self) -> None:
        try:
            self._instrument.set_rate(self._slew_input.value())
        except InstrumentError as exc:
            logger.error("Set slew rate failed: %s", exc)
            QMessageBox.critical(self, "Write Error", str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_connected_state(self, connected: bool) -> None:
        if connected:
            self._poll_thread.start()
        else:
            self._poll_thread.quit()
            self._poll_thread.wait()
        self._connection_status.setText("Status: Connected" if connected else "Status: Disconnected")
        self._connect_btn.setText("Disconnect" if connected else "Connect")
        self._mode_switch.setEnabled(connected)
        self._setpoint_input.setEnabled(connected)
        self._step_input.setEnabled(connected)
        self._slew_input.setEnabled(connected)

    def _update_pressure_color(self, pressure: float) -> None:
        """Colour the pressure label based on proximity to setpoint (control mode only)."""
        is_control = self._mode_switch.isChecked()
        if not is_control:
            self._pressure_label.setStyleSheet("")
            return
        at_setpoint = abs(pressure - self._setpoint_input.value()) <= SETPOINT_TOLERANCE_BAR
        color = "#2ecc71" if at_setpoint else "#3498db"  # green / blue
        self._pressure_label.setStyleSheet(f"color: {color};")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._poll_thread.isRunning():
            self._poll_thread.quit()
            self._poll_thread.wait()
        self._instrument.disconnect()
        event.accept()


