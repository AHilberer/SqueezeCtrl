# SqueezeCtrl

A small PyQt5 desktop app for controlling a GE Druck PACE Series pressure
controller over VISA/SCPI (USB or Ethernet).

## Features

- Switch between MEASURE and CONTROL mode
- Set a target pressure and slew rate, with live pressure/rate readouts
- Run an automated pressure cycling sequence — upper/lower pressure,
  cycle count, start/stop, and a remaining-cycles counter — from a
  dockable side panel
- Auto-discover the instrument over USB/Ethernet, or connect by IP
  directly for static-IP Ethernet instruments that don't answer discovery

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
if nothing is found, it falls back to asking for an IP address directly.

## Raw instrument test notebook

`notebooks/instrument_raw_tests.ipynb` exercises the VISA/SCPI commands
directly, outside the GUI — useful for checking a command against real
hardware. Open it with:

```sh
uv run notebook
```
