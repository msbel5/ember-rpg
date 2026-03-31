# Automation Stack

```mermaid
flowchart TD
    A["Scenario TOML"] --> B["automation.runner"]
    B --> C["Preflight environment check"]
    C --> D["headless_godot executor"]
    C --> E["win32_desktop executor"]
    D --> F["godot/automation_bridge.gd"]
    F --> G["Logical mouse/key/text commands"]
    F --> H["Viewport capture / recording"]
    E --> I["Window activation"]
    E --> J["Desktop mouse/key forwarding"]
    E --> K["OS screenshot proof"]
```

## Policy

- `computer_use` is not the primary Godot QA path.
- `headless_godot` is the preferred deterministic path.
- `win32_desktop` is the desktop proof fallback.
- The desktop runner must fail early if dependencies are missing instead of
  pretending the scenario was executed.
