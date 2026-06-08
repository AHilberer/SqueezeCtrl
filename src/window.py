"""Main application window."""

import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import (
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


class SteppedSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox whose arrow step is driven by an external step spinbox."""

    def __init__(self, step_source: QDoubleSpinBox, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step_source = step_source

    def stepBy(self, steps: int) -> None:
        step = self._step_source.value()
        self.setValue(self.value() + steps * step)
        self.editingFinished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(*WINDOW_GEOMETRY)

        self._instrument = PressureInstrument()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(200)
        self._poll_timer.timeout.connect(self._on_refresh)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setSpacing(12)

        root.addLayout(self._build_connection_row())
        root.addWidget(self._build_mode_button())
        root.addWidget(self._build_readout_section())
        root.addLayout(self._build_setpoint_section())
        root.addLayout(self._build_slew_section())

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def _build_connection_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._address_input = QLineEdit()
        self._address_input.setPlaceholderText(
            "Enter USB address (e.g., USB0::0x1234::0x5678::INSTR)"
        )

        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self._on_connect)

        layout.addWidget(self._address_input)
        layout.addWidget(connect_btn)
        return layout

    def _build_mode_button(self) -> QPushButton:
        self._mode_btn = QPushButton("MEASURE")
        self._mode_btn.setEnabled(False)
        self._mode_btn.setCheckable(True)
        self._mode_btn.setMinimumHeight(56)

        btn_font = QFont()
        btn_font.setPointSize(16)
        btn_font.setBold(True)
        self._mode_btn.setFont(btn_font)

        self._mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border-radius: 8px;
            }
            QPushButton:checked {
                background-color: #e07b39;
            }
            QPushButton:disabled {
                background-color: #aaaaaa;
            }
        """)
        self._mode_btn.clicked.connect(self._on_toggle_mode)
        return self._mode_btn

    def _build_readout_section(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Sunken)

        big_font = QFont()
        big_font.setPointSize(22)
        big_font.setBold(True)

        unit_font = QFont()
        unit_font.setPointSize(12)

        layout = QHBoxLayout(frame)
        layout.setSpacing(32)

        for attr, title, unit in (
            ("_pressure_label", "Pressure", UNIT_PRESSURE),
            ("_rate_label", "Rate", UNIT_RATE),
        ):
            col = QVBoxLayout()
            col.setAlignment(Qt.AlignCenter)

            title_lbl = QLabel(title)
            title_lbl.setAlignment(Qt.AlignCenter)

            value_lbl = QLabel("—")
            value_lbl.setFont(big_font)
            value_lbl.setAlignment(Qt.AlignCenter)
            setattr(self, attr, value_lbl)

            unit_lbl = QLabel(unit)
            unit_lbl.setFont(unit_font)
            unit_lbl.setAlignment(Qt.AlignCenter)

            col.addWidget(title_lbl)
            col.addWidget(value_lbl)
            col.addWidget(unit_lbl)
            layout.addLayout(col)

        # Secondary readout — positive source pressure
        layout.addSpacing(16)
        src_col = QVBoxLayout()
        src_col.setAlignment(Qt.AlignCenter)

        src_title = QLabel("Source Pressure")
        src_title.setAlignment(Qt.AlignCenter)

        self._source_pressure_label = QLabel("—")
        src_font = QFont()
        src_font.setPointSize(14)
        self._source_pressure_label.setFont(src_font)
        self._source_pressure_label.setAlignment(Qt.AlignCenter)

        src_unit = QLabel(UNIT_PRESSURE)
        src_unit.setAlignment(Qt.AlignCenter)

        src_col.addWidget(src_title)
        src_col.addWidget(self._source_pressure_label)
        src_col.addWidget(src_unit)
        layout.addLayout(src_col)

        return frame

    def _build_setpoint_section(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._step_input = QDoubleSpinBox()
        self._step_input.setDecimals(SETPOINT_DECIMALS)
        self._step_input.setRange(0.0001, SETPOINT_MAX)
        self._step_input.setValue(SETPOINT_STEP_DEFAULT)

        self._setpoint_input = SteppedSpinBox(step_source=self._step_input)
        self._setpoint_input.setDecimals(SETPOINT_DECIMALS)
        self._setpoint_input.setRange(SETPOINT_MIN, SETPOINT_MAX)
        self._setpoint_input.setValue(SETPOINT_DEFAULT)
        self._setpoint_input.setEnabled(False)
        self._setpoint_input.editingFinished.connect(self._on_send_setpoint)

        self._step_input.setEnabled(False)

        layout.addWidget(QLabel("Set-Point Pressure:"))
        layout.addWidget(self._setpoint_input)
        layout.addWidget(QLabel(UNIT_PRESSURE))
        layout.addSpacing(16)
        layout.addWidget(QLabel("Step:"))
        layout.addWidget(self._step_input)
        layout.addWidget(QLabel(UNIT_PRESSURE))
        return layout

    def _build_slew_section(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self._slew_input = QDoubleSpinBox()
        self._slew_input.setDecimals(SLEW_DECIMALS)
        self._slew_input.setRange(SLEW_MIN, SLEW_MAX)
        self._slew_input.setValue(SLEW_DEFAULT)
        self._slew_input.setEnabled(False)
        self._slew_input.editingFinished.connect(self._on_send_slew)

        layout.addWidget(QLabel("Slew Rate:"))
        layout.addWidget(self._slew_input)
        layout.addWidget(QLabel(UNIT_RATE))
        layout.addStretch()
        return layout

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_connect(self) -> None:
        address = self._address_input.text().strip()
        try:
            self._instrument.connect(address)
            self._set_connected_state(True)
            # Read initial mode from instrument
            try:
                mode = self._instrument.read_mode()
                self._apply_mode_ui(mode)
            except InstrumentError as exc:
                logger.warning("Could not read initial mode: %s", exc)
            QMessageBox.information(self, "Connection", "Connected successfully!")
        except InstrumentError as exc:
            logger.error("Connection failed: %s", exc)
            QMessageBox.critical(self, "Connection Error", str(exc))

    def _on_toggle_mode(self) -> None:
        # Button is checkable: checked = CONTROL, unchecked = MEASURE
        want_control = self._mode_btn.isChecked()
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
            # Revert button state
            self._mode_btn.setChecked(not want_control)

    def _apply_mode_ui(self, mode: ControlMode) -> None:
        is_control = mode is ControlMode.CONTROL
        self._mode_btn.setChecked(is_control)
        self._mode_btn.setText("CONTROL" if is_control else "MEASURE")
        if not is_control:
            self._pressure_label.setStyleSheet("")

    def _on_refresh(self) -> None:
        try:
            pressure = self._instrument.read_pressure()
            rate = self._instrument.read_rate()
            source = self._instrument.read_source_pressure()
            self._pressure_label.setText(str(pressure))
            self._rate_label.setText(str(rate))
            self._source_pressure_label.setText(str(source))
            self._update_pressure_color(pressure)
        except InstrumentError as exc:
            logger.warning("Poll failed: %s", exc)

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
            self._poll_timer.start()
        else:
            self._poll_timer.stop()
        self._mode_btn.setEnabled(connected)
        self._setpoint_input.setEnabled(connected)
        self._step_input.setEnabled(connected)
        self._slew_input.setEnabled(connected)

    def _update_pressure_color(self, pressure: float) -> None:
        """Colour the pressure label based on proximity to setpoint (control mode only)."""
        is_control = self._mode_btn.isChecked()
        if not is_control:
            self._pressure_label.setStyleSheet("")
            return
        at_setpoint = abs(pressure - self._setpoint_input.value()) <= SETPOINT_TOLERANCE_BAR
        color = "#2ecc71" if at_setpoint else "#3498db"  # green / blue
        self._pressure_label.setStyleSheet(f"color: {color};")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._instrument.disconnect()
        event.accept()


