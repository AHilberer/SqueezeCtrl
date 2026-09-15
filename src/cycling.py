"""Automated upper/lower pressure cycling sequence."""

import logging
from enum import Enum, auto

from PyQt5.QtCore import QObject, pyqtSignal

from .config import SETPOINT_TOLERANCE_BAR
from .instrument import InstrumentError, PressureInstrument

logger = logging.getLogger(__name__)


class CycleState(Enum):
    IDLE = auto()
    GOING_TO_UPPER = auto()
    GOING_TO_LOWER = auto()


class CycleController(QObject):
    """Drives the instrument through repeated upper/lower pressure cycles.

    A "cycle" is one upper -> lower round trip, starting with a move to
    upper. Progress is driven by feeding it live pressure readings via
    on_reading(); it decides a target has been reached once the reading is
    within SETPOINT_TOLERANCE_BAR of it, and then moves to the next leg.
    """

    target_changed = pyqtSignal(float)
    remaining_changed = pyqtSignal(int)
    state_changed = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, instrument: PressureInstrument) -> None:
        super().__init__()
        self._instrument = instrument
        self._state = CycleState.IDLE
        self._upper = 0.0
        self._lower = 0.0
        self._remaining = 0

    @property
    def is_running(self) -> bool:
        return self._state is not CycleState.IDLE

    def start(self, upper: float, lower: float, cycles: int) -> None:
        """Begin cycling between *upper* and *lower* (Bar) *cycles* times."""
        if upper <= lower:
            raise ValueError("Upper pressure must be greater than lower pressure.")
        if cycles < 1:
            raise ValueError("Number of cycles must be at least 1.")

        self._upper = upper
        self._lower = lower
        self._remaining = cycles
        self.remaining_changed.emit(self._remaining)

        try:
            self._instrument.set_control(upper)
        except InstrumentError as exc:
            self.error.emit(str(exc))
            return

        self._state = CycleState.GOING_TO_UPPER
        self.target_changed.emit(upper)
        self.state_changed.emit("Going to upper")
        logger.info("Cycling started: upper=%.4f lower=%.4f cycles=%d", upper, lower, cycles)

    def stop(self) -> None:
        if self._state is CycleState.IDLE:
            return
        self._state = CycleState.IDLE
        self.state_changed.emit("Stopped")
        logger.info("Cycling stopped by user")

    def on_reading(self, pressure: float) -> None:
        """Feed a live pressure reading; advances the sequence when a target is reached."""
        if self._state is CycleState.IDLE:
            return

        target = self._upper if self._state is CycleState.GOING_TO_UPPER else self._lower
        if abs(pressure - target) > SETPOINT_TOLERANCE_BAR:
            return

        if self._state is CycleState.GOING_TO_UPPER:
            self._move_to(CycleState.GOING_TO_LOWER, self._lower)
            self.state_changed.emit("Going to lower")
            return

        # Reached lower after having reached upper: one full cycle complete.
        self._remaining -= 1
        self.remaining_changed.emit(self._remaining)
        if self._remaining <= 0:
            self._state = CycleState.IDLE
            self.state_changed.emit("Finished")
            self.finished.emit()
            logger.info("Cycling finished")
            return

        self._move_to(CycleState.GOING_TO_UPPER, self._upper)
        self.state_changed.emit("Going to upper")

    def _move_to(self, state: CycleState, target: float) -> None:
        try:
            self._instrument.set_pressure(target)
        except InstrumentError as exc:
            self._state = CycleState.IDLE
            self.error.emit(str(exc))
            return
        self._state = state
        self.target_changed.emit(target)
