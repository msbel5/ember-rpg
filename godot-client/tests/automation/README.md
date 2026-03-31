# Ember RPG Automation Stack

This directory is the authoritative automation surface for Godot UI proof.

## Layers

- `headless_godot`
  - Deterministic, scene/logical-coordinate automation through `godot/automation_bridge.gd`
  - Preferred for repeatable UI flow tests
- `win32_desktop`
  - Real window activation, keyboard/mouse forwarding, OS screenshots
  - Fallback for desktop proof only

## Desktop Environment

Create a dedicated Python environment for desktop automation:

```powershell
py -3.10 -m venv .venv-automation
.\\.venv-automation\\Scripts\\Activate.ps1
pip install -r godot-client/tests/automation/requirements-desktop.txt
```

Required packages:

- `pywin32`
- `Pillow`
- `requests`

The runner now performs a preflight environment check before launching the
desktop executor. If the environment is incomplete, the run fails early with a
report that names the missing packages and the install command.

## Coordinate Policy

- Prefer `headless_godot` actions and logical scene coordinates
- Do not treat OS pixel clicks as the default control path
- Reserve desktop pixel forwarding for smoke checks, window activation, and
  last-mile screenshot proof

## Screenshot Policy

- `capture_viewport` is scene/viewport proof
- `capture_os` is desktop/window proof
- Headless synthetic captures are explicitly marked synthetic and are not
  desktop-equivalent evidence
