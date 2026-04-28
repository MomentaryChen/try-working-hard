# try-working-hard

**Languages:** English (this file) · [正體中文](README.zh-TW.md)

Nudges the mouse along a small path (line, circle, or square) and restores it **only after** the chosen interval elapses with **no keyboard or mouse input** (Windows `GetLastInputInfo`), with a GUI for the interval and options. For **lawful personal use only** (for example, keeping the screen awake during a presentation or reading). You must comply with applicable laws, employer or school policies, and service terms.

## Requirements

- **Windows** (cursor movement uses the Win32 API)
- **Python** 3.10 or newer
- **[uv](https://docs.astral.sh/uv/)** is recommended to manage the environment and run the app

## Install and run

From the project root:

```powershell
uv sync
uv run try-working-hard
```

Or as a module:

```powershell
uv run python -m mouse_jiggler
```

### PySide6 dashboard prototype

This repository also includes a modular PySide6 desktop dashboard scaffold with a modern dark theme and MVVM-style page routing:

```powershell
uv run python main.py
```

Structure overview:

- `main.py` entry point
- `ui/` window shell and navigation view model
- `views/` page-level widgets (Dashboard, Tasks, Settings)
- `components/` reusable UI widgets (cards, sidebar button, table)
- `styles/styles.qss` centralized theme styling
- `assets/icons/` SVG Material-style sidebar icons

Included UX enhancements:

- Animated active-page indicator bar in the sidebar
- Real `pyqtgraph` integration on the dashboard (sample trend lines with hover crosshair/tooltip)
- SVG icon rendering per navigation button
- One-time productivity reminder with "do not show again" and reset in Settings
- Global toast notifications for lightweight user feedback
- Keyboard shortcuts: `Ctrl+1/2/3`, `Ctrl+N`, `Delete`, `?`

### Windows executable (no Python)

Tagged releases on **GitHub** attach a **single-file** build: `try-working-hard.exe` (PyInstaller, one-file, no console). Download it from the **Releases** page for the version you want (for example `v1.0.0`) and run the file.

- How the `.exe` is built locally or in CI: [docs/WINDOWS-BUILD.md](docs/WINDOWS-BUILD.md) (also covers SmartScreen, alternatives such as Briefcase at a high level).
- **Tag a release:** push a `v*` tag (for example `v1.0.0`); [`.github/workflows/release.yml`](.github/workflows/release.yml) runs tests, builds the executable, and uploads it to that release.

### Keyboard and accessibility

- **F1** opens a help dialog with shortcuts. **F2 / F3 / F4** switch main areas; on **Home → Control**, **F5** starts and **Shift+F5** stops when available; **Enter** / **Esc** do the same while the **main window is visible** (they do nothing when the app is only in the **system tray**). **F6** toggles Control / Log. You can **click the interval, interval jitter, nudge, path speed, and path labels** to focus the matching field; **30s / 1m / 5m / 10m** under the interval field apply a quick preset. **Tab / Shift+Tab** moves between controls.
- CustomTkinter draws many controls on a **canvas**, so **screen reader** coverage is not the same as for fully native Win32 UIs. Details: [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md).

## Usage

1. The main window **opens maximized**; use the title bar to restore or resize as needed.
2. On each normal launch (not `--start-in-tray`), the app shows a **usage reminder** dialog before control interaction. Continue only if your use is lawful and compliant with employer/school/service rules.
3. On **Settings**, the page title stays fixed while options are shown in a bordered card; **scroll inside the card** when the window is short to reach every control. Choose **Appearance** (**Dark** or **Light** -> `ui_theme`, default **light**) and language (**繁中** / English). Optionally enable the schedule window: the UI still provides **Start** / **End** in **HH:MM** (end exclusive), and config now supports richer rules: multiple segments in `schedule_window_segments_text` (for example `09:00-12:00,13:00-18:00,21:00-23:00`), weekend toggle via `schedule_include_weekends`, and optional cron-like expressions via `schedule_cron_text` (one or more 5-field expressions separated by `;`). Existing keys `schedule_window_start_text` / `schedule_window_end_text` remain supported for backward compatibility. When schedule is on, **Home** shows a summary line below the status strip.
4. Enter the **interval** (minimum **idle** time with no keyboard/mouse input before a nudge); use **min** or **sec** to pick units (minutes allow decimals, e.g. `0.5` ≈ 30 seconds, minimum **0.1** min; seconds follow the same minimum in seconds as **0.1** min). Under the field, use **30s / 1m / 5m / 10m** for a quick set.
5. Optionally set **Interval jitter (± sec)** (`0` = fixed spacing): each idle-required spacing is drawn uniformly in `[interval − N, interval + N]` seconds (floored at the same minimum as the main interval). Range **0–3600**; saved as `interval_jitter_text`.
6. Set **nudge size in pixels** (integer, **0–500**). Meaning depends on the path: line = horizontal distance; circle = radius; square = edge length. **0** skips movement for that tick. Default is **100**.
7. Set **path speed** (integer, **1–10**): how quickly the app traces the line, circle, or square (higher = faster). Default is **5**. Stored in `config.json` as `path_speed_text`.
8. Choose **motion path**: **Line**, **Circle**, or **Square**—this matches how the nudge size is applied. Saved in `config.json` as `motion_pattern`. The home control area **scrolls** if the window is short.
9. Click **Start** to begin the schedule; **Stop** ends it. Use **Home** in the sidebar, then the **Control / Log** segmented control to switch between the control panel and the **log** view.
10. While running, the **status strip** at the top of Home shows the **countdown** to the next possible nudge (`mm:ss`, or `h:mm:ss` after one hour), based on idle time and spacing (at least one full interval between nudges while you stay idle), and a color cue—or a pause countdown when the work-hours limit applies; when stopped, the strip is neutral.
11. **By default**, closing the window **stops the schedule and exits** the app. If you enable **Minimize to the system tray when closing the window**, closing hides the window and keeps a notification icon while the **schedule keeps running**; right‑click the icon for **Show window** or **Exit** (labels follow the selected language). Advanced: `uv run python -m mouse_jiggler --start-in-tray` (or the same flag on a frozen **.exe`) starts in the tray only, without showing the main window at first.
12. On **Settings**, use **Open config file** to open `config.json` (under `%APPDATA%\try-working-hard\` on Windows, or `~/.try-working-hard/` if `APPDATA` is unset) in the default application; if the file does not exist yet, the app writes the current settings first.
13. **Analytics** (sidebar) shows **Matplotlib** charts (nudge counts, daily scheduled uptime, path mix) and mirrors the **Home** log in a read-only text area. Usage stats are persisted as **`analytics.json`** in the **same folder** as `config.json`.

## Technical notes

- GUI: **CustomTkinter** — **light** mode: built-in `blue` theme, **#F9FAFB** app background, **#F3F4F6** sidebar, **#FFFFFF** card panels. **Dark** mode: `dark` + `dark-blue` with a dark surface palette. **Home** uses a segmented control for Control / Log.
- **Analytics**: **Matplotlib** figures embedded via **TkAgg**; persisted aggregates in **`analytics.json`** next to **`config.json`**.
- Mouse: **ctypes** calling `user32.GetCursorPos` / `SetCursorPos`; schedule uses `user32.GetLastInputInfo` with `kernel32.GetTickCount` for idle time
- Tray: **pystray**; icon: **Pillow** (shared PNG for window, tray, and—when rebuilt—[`packaging/app.ico`](packaging/app.ico) for the `.exe`; see [docs/WINDOWS-BUILD.md](docs/WINDOWS-BUILD.md))

## Limitations

- Behavior may differ when the screen is locked or in some remote-desktop setups.
- Do not use this tool to bypass security, monitoring, or compliance controls you are required to follow.

## Disclaimer

This software is provided **“as is”**, **without warranty of any kind**, whether express or implied (including but not limited to merchantability, fitness for a particular purpose, or non‑infringement). You **choose to use** it **at your own risk**.

In no event shall the authors or contributors be liable for **any direct, indirect, incidental, special, consequential, or punitive damages** arising out of or related to use or inability to use this software (including but not limited to loss of data, business interruption, hardware damage, or consequences of violating employer rules or laws)—**even if advised of the possibility** of such damages.

You agree to use this software only in a manner that **complies with applicable laws** and with employer, school, contractual, and service obligations. You **must not** use it to circumvent security controls, labor or attendance monitoring, audits, license checks, or for any unlawful or improper purpose. **You bear sole responsibility** for any legal or financial liability arising from your use.

## License

This project is licensed under the **MIT License**. See the [`LICENSE`](LICENSE) file in the repository root for the full text.

In short: you may use, modify, distribute, and sublicense the software subject to retaining the copyright and permission notice; the software is still provided **as-is, without warranty**, consistent with the disclaimer above and the full `LICENSE`.
