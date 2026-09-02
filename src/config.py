"""Application-wide constants and configuration."""

# VISA / instrument
INSTRUMENT_TIMEOUT_MS: int = 5000

# Ethernet fallback: static-IP instruments often don't answer VISA's discovery
# broadcast, so this pre-fills the manual "Connect by IP" prompt.
DEFAULT_INSTRUMENT_IP = "192.168.1.6"

# SCPI commands
CMD_READ_PRESSURE = ":SENSe:PRESsure?"
CMD_READ_RATE = ":SENSe:PRESsure:SLEW?"
CMD_READ_SOURCE_PRESSURE = ":SOURce:PRESsure:COMPensate 1?"
CMD_SET_PRESSURE = "SET:PRES"
CMD_SET_RATE = "SET:RATE"
CMD_SET_SOURCE = ":SOUR"
CMD_SET_OUTPUT = ":OUTP"
CMD_QUERY_MODE = ":SYST:SET?"

# Units
UNIT_PRESSURE = "bar"
UNIT_RATE = "bar/min"

# Spinbox defaults
SETPOINT_DEFAULT = 0.0
SETPOINT_MIN = 0.0
SETPOINT_MAX = 20.0
SETPOINT_DECIMALS = 4
SETPOINT_STEP_DEFAULT = 0.1

SLEW_DEFAULT = 1.0
SLEW_MIN = 0.0
SLEW_MAX = 100.0
SLEW_DECIMALS = 3

# UI
WINDOW_TITLE = "Pressure Controller"
WINDOW_GEOMETRY = (300, 300, 680, 380)  # x, y, w, h

SETPOINT_TOLERANCE_BAR = 0.02
