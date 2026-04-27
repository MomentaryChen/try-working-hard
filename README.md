# try-working-hard

**Languages:** English (this file) · [正體中文](README.zh-TW.md)

Periodically nudges the mouse by one pixel and restores it, with a GUI to set the interval (minutes). For **lawful personal use only** (for example, keeping the screen awake during a presentation or reading). You must comply with applicable laws, employer or school policies, and service terms.

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

### Windows executable (no Python)

Tagged releases on **GitHub** attach a **single-file** build: `try-working-hard.exe` (PyInstaller, one-file, no console). Download it from the **Releases** page for the version you want (for example `v1.0.0`) and run the file.

- How the `.exe` is built locally or in CI: [docs/WINDOWS-BUILD.md](docs/WINDOWS-BUILD.md) (also covers SmartScreen, alternatives such as Briefcase at a high level).
- **Tag a release:** push a `v*` tag (for example `v1.0.0`); [`.github/workflows/release.yml`](.github/workflows/release.yml) runs tests, builds the executable, and uploads it to that release.

### Keyboard and accessibility

- **F1** opens a help dialog with shortcuts. **F2 / F3 / F4** switch main areas; on **Home → Control**, **F5** starts and **Shift+F5** stops when available; **F6** toggles Control / Log. You can **click the interval, nudge, and active-motion labels** to focus the matching field. **Tab / Shift+Tab** moves between controls.
- CustomTkinter draws many controls on a **canvas**, so **screen reader** coverage is not the same as for fully native Win32 UIs. Details: [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md).

## Usage

1. Use the sidebar **繁中 / English** segmented control to switch the UI language.
2. Enter the **interval in minutes** (decimals allowed, e.g. `0.5` ≈ 30 seconds; minimum **0.1** minutes).
3. Set **nudge size in pixels** (integer, **0–500**): the cursor moves horizontally by this amount, then returns; **0** skips movement for that tick. Default is **100**.
4. Set **active motion (seconds)** (**0–600**, decimals allowed): after each interval fires, the app repeats the nudge at a short cadence for this many seconds, then waits for the next interval. **0** means a single nudge per tick (legacy behavior). If nudge size is **0**, this duration is ignored.
5. Click **Start** to begin the schedule; **Stop** ends it. Use the **segmented control** (or matching sidebar items) to switch between the control panel and the **log** view.
6. While running, the **status line** at the top of Home shows the **countdown** (`mm:ss`, or `h:mm:ss` after one hour). During an active-motion phase, it indicates **active motion** and counts down to the end of that phase.
7. **By default**, closing the window **stops the schedule and exits** the app. If you enable **Minimize to the system tray when closing the window**, closing hides the window and keeps a notification icon while the **schedule keeps running**; right‑click the icon for **Show window** or **Exit** (labels follow the selected language).
8. On **Settings**, use **Open config file** to open `config.json` (under `%APPDATA%\try-working-hard\` on Windows, or `~/.try-working-hard/` if `APPDATA` is unset) in the default application; if the file does not exist yet, the app writes the current settings first.

## Technical notes

- GUI: **CustomTkinter** (dark / `dark-blue` theme, sidebar + segmented control)
- Mouse: **ctypes** calling `user32.GetCursorPos` / `SetCursorPos`
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
