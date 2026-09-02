"""VISA instrument abstraction for the pressure controller."""

import logging
import threading
from enum import Enum

import pyvisa

from .config import (
    CMD_QUERY_MODE,
    CMD_READ_PRESSURE,
    CMD_READ_RATE,
    CMD_READ_SOURCE_PRESSURE,
    CMD_SET_OUTPUT,
    CMD_SET_PRESSURE,
    CMD_SET_RATE,
    INSTRUMENT_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)


class InstrumentError(Exception):
    """Raised when an instrument operation fails."""


class ControlMode(Enum):
    MEASURE = "MEAS"
    CONTROL = "CONT"


class PressureInstrument:
    """Wraps a pyvisa resource for a SCPI-based pressure controller."""

    def __init__(self) -> None:
        self._rm = pyvisa.ResourceManager()
        self._resource: pyvisa.resources.Resource | None = None
        # Serializes access to _resource: the UI thread issues writes (setpoint
        # edits, mode changes) while a background thread polls readings, and
        # pyvisa resources aren't safe for concurrent use from multiple threads.
        self._io_lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._resource is not None

    def connect(self, address: str) -> None:
        """Open a VISA connection to the instrument at *address*."""
        if not address:
            raise InstrumentError("VISA address must not be empty.")
        try:
            resource = self._rm.open_resource(address)
            resource.timeout = INSTRUMENT_TIMEOUT_MS
            self._resource = resource
            logger.info("Connected to instrument at %s", address)
        except pyvisa.VisaIOError as exc:
            raise InstrumentError(f"Could not connect to {address!r}: {exc}") from exc

    def list_candidate_resources(self) -> list[str]:
        """Return VISA resources limited to USB and Ethernet transports."""
        try:
            resources = self._rm.list_resources()
        except pyvisa.VisaIOError as exc:
            raise InstrumentError(f"Could not list VISA resources: {exc}") from exc

        candidates = []
        for address in resources:
            upper = address.upper()
            if upper.startswith("USB") or upper.startswith("TCPIP"):
                candidates.append(address)
        return candidates

    def find_recognized_resources(self) -> list[str]:
        """Return resources that answer like a supported pressure controller."""
        recognized: list[str] = []
        for address in self.list_candidate_resources():
            if self._looks_like_controller(address):
                recognized.append(address)
        return recognized

    def disconnect(self) -> None:
        """Close the VISA connection if open."""
        if self._resource is not None:
            try:
                with self._io_lock:
                    self._resource.close()
                logger.info("Instrument disconnected.")
            except pyvisa.VisaIOError as exc:
                logger.warning("Error while closing instrument: %s", exc)
            finally:
                self._resource = None

    def read_pressure(self) -> float:
        """Return the current output pressure in Bar."""
        return self._query_float(CMD_READ_PRESSURE)

    def read_rate(self) -> float:
        """Return the current output slew rate in Bar/min."""
        return self._query_float(CMD_READ_RATE)

    def read_source_pressure(self) -> float:
        """Return the positive source pressure (Bar)."""
        return self._query_float(CMD_READ_SOURCE_PRESSURE)

    def read_mode(self) -> ControlMode:
        """Query the current operating mode (MEASURE or CONTROL)."""
        resource = self._assert_connected()
        try:
            with self._io_lock:
                raw = resource.query(CMD_QUERY_MODE).strip()
            # Response format: ":SYST:SET MEAS, 0.0" or ":SYST:SET CONT, 100.0"
            upper = raw.upper()
            if "CONT" in upper:
                return ControlMode.CONTROL
            return ControlMode.MEASURE
        except pyvisa.VisaIOError as exc:
            raise InstrumentError(f"Mode query failed: {exc}") from exc

    def set_control(self, setpoint: float) -> None:
        """Switch to control mode with the given setpoint (Bar)."""
        self._write(f"{CMD_SET_PRESSURE} {setpoint}")
        self._write(f"{CMD_SET_OUTPUT} 1")
        logger.info("Switched to CONTROL mode, setpoint=%.4f", setpoint)

    def set_measure(self) -> None:
        """Switch to measure mode (output off)."""
        self._write(f"{CMD_SET_OUTPUT} 0")
        logger.info("Switched to MEASURE mode")

    def set_pressure(self, value: float) -> None:
        """Send the set-point pressure (Bar) to the instrument."""
        self._write(f"{CMD_SET_PRESSURE} {value}")

    def set_rate(self, value: float) -> None:
        """Send the slew rate (Bar/min) to the instrument."""
        self._write(f"{CMD_SET_RATE} {value}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assert_connected(self) -> pyvisa.resources.Resource:
        if self._resource is None:
            raise InstrumentError("Not connected to any instrument.")
        return self._resource

    def _query_float(self, command: str) -> float:
        resource = self._assert_connected()
        try:
            with self._io_lock:
                raw = resource.query(command)
        except pyvisa.VisaIOError as exc:
            raise InstrumentError(f"Query {command!r} failed: {exc}") from exc

        # Responses echo the command mnemonic before the value, e.g.
        # ":SENS:PRES 0.002774" — the value is always the last whitespace-
        # separated token, whether or not an echo prefix is present.
        tokens = raw.split()
        if not tokens:
            raise InstrumentError(f"Empty response to {command!r}")
        try:
            return float(tokens[-1])
        except ValueError as exc:
            raise InstrumentError(
                f"Unexpected response to {command!r}: {raw!r} ({exc})"
            ) from exc

    def _write(self, command: str) -> None:
        resource = self._assert_connected()
        try:
            with self._io_lock:
                resource.write(command)
            logger.debug("Sent: %s", command)
        except pyvisa.VisaIOError as exc:
            raise InstrumentError(f"Write {command!r} failed: {exc}") from exc

    def _looks_like_controller(self, address: str) -> bool:
        """Probe an address with a mode query to identify compatible devices."""
        resource: pyvisa.resources.Resource | None = None
        try:
            resource = self._rm.open_resource(address)
            resource.timeout = INSTRUMENT_TIMEOUT_MS
            raw = resource.query(CMD_QUERY_MODE).strip().upper()
            return "MEAS" in raw or "CONT" in raw
        except pyvisa.VisaIOError:
            return False
        finally:
            if resource is not None:
                try:
                    resource.close()
                except pyvisa.VisaIOError:
                    logger.debug("Probe close failed for %s", address)

    def __del__(self) -> None:
        self.disconnect()
