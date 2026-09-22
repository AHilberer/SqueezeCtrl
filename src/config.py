"""Application-wide constants and configuration."""

# VISA / instrument
INSTRUMENT_TIMEOUT_MS: int = 5000
POLL_INTERVAL_MS: int = 250

# Ethernet fallback: static-IP instruments often don't answer VISA's discovery
# broadcast, so this pre-fills the manual "Connect by IP" prompt.
DEFAULT_INSTRUMENT_IP = "192.168.1.6"

# SCPI commands (verified against the GE Druck PACE Series SCPI manual, K0472)
CMD_READ_PRESSURE = ":SENSe:PRESsure?"
CMD_READ_RATE = ":SENSe:PRESsure:SLEW?"
# COMPensate takes the source index (1=+ve, 2=-ve) as a numeric suffix
# directly on the mnemonic, not as a value before the '?'.
CMD_READ_SOURCE_PRESSURE = ":SOURce:PRESsure:COMPensate1?"
CMD_SET_PRESSURE = ":SOURce:PRESsure"
CMD_SET_RATE = ":SOURce:PRESsure:SLEW"
CMD_SET_OUTPUT = ":OUTP"
# :SYST:SET? is documented as "only effective at switch-on condition" -- it
# reports the power-on default mode/setpoint, NOT the instrument's live
# running state, so a device already in CONTROL mode can still answer this
# with MEAS. It's only used here to sniff for a compatible controller during
# resource discovery. For live state, use CMD_QUERY_OUTPUT_STATE / CMD_QUERY_SETPOINT.
CMD_QUERY_MODE = ":SYST:SET?"
# Live controller on/off state (0/1), matching the CMD_SET_OUTPUT (:OUTP) write.
CMD_QUERY_OUTPUT_STATE = ":OUTPut:STATe?"
# Live commanded setpoint, matching the CMD_SET_PRESSURE (:SOUR:PRES) write.
CMD_QUERY_SETPOINT = ":SOURce:PRESsure?"
# Readback of the configured target slew rate (the :SOURce: register CMD_SET_RATE
# writes to), as opposed to CMD_READ_RATE which is the live/actual slew under
# :SENSe:.
CMD_READ_CONFIGURED_RATE = ":SOURce:PRESsure:SLEW?"
CMD_QUERY_UNIT = ":UNIT:PRESsure?"

# The GE Druck PACE SCPI manual (K0472, ":SOUR:PRES:SLEW" / ":SENS:PRES:SLEW?")
# documents slew rate as being in the instrument's pressure unit PER SECOND.
# Verified against real hardware: this is wrong for this instrument -- setting
# 10 bar/min on the front panel and reading CMD_READ_CONFIGURED_RATE back
# raw gives 10, not 10/60. The register already matches the front panel's
# Bar/min directly, so no time-base conversion is applied in instrument.py.

# This app assumes the instrument's own pressure-unit setting (front panel /
# :UNIT:PRES) is BAR, and doesn't convert pressure/setpoint values for any
# other unit -- the instrument can be set to mbar, psi, kPa, etc. by the user
# independently of this app, which would silently misinterpret every
# pressure/setpoint/rate value exchanged. read_pressure_unit() lets callers
# check this and warn instead of guessing at a conversion.
EXPECTED_PRESSURE_UNIT = "BAR"

# Units
UNIT_PRESSURE = "bar"
UNIT_RATE = "bar/min"

# Spinbox defaults
SETPOINT_DEFAULT = 0.0
SETPOINT_MIN = 0.0
SETPOINT_MAX = 200.0
SETPOINT_DECIMALS = 3
SETPOINT_STEP_DEFAULT = 0.1

SLEW_DEFAULT = 1.0
SLEW_MIN = 0.0
SLEW_MAX = 100.0
SLEW_DECIMALS = 3

# Pressure cycling sequence defaults
CYCLE_UPPER_DEFAULT = 1.0
CYCLE_LOWER_DEFAULT = 0.0
CYCLE_COUNT_DEFAULT = 10
CYCLE_COUNT_MAX = 9999

# UI
WINDOW_TITLE = "Pressure Controller"
WINDOW_GEOMETRY = (300, 300, 680, 380)  # x, y, w, h

SETPOINT_TOLERANCE_BAR = 0.02

# Live readouts are formatted to this many decimal places so the UI doesn't
# jitter as the instrument returns varying-precision values.
READOUT_DECIMALS = 3
