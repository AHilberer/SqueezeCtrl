# SqueezeCtrl

A small PyQt5 desktop app for controlling a GE Druck PACE Series pressure
controller over VISA/SCPI (USB or Ethernet). Lets you switch between
MEASURE and CONTROL mode, set a target pressure and slew rate, and watch
live pressure/rate readouts.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```sh
uv sync
```

## Run

```sh
uv run SqueezeCtrl
```

On connect, the app tries to auto-discover the instrument over USB/Ethernet;
if nothing is found (common for static-IP Ethernet instruments), it falls
back to asking for an IP address directly.

## Raw instrument test notebook

`notebooks/instrument_raw_tests.ipynb` exercises the VISA/SCPI commands
directly, outside the GUI — useful for checking a command against real
hardware. Open it with:

```sh
uv run notebook
```
