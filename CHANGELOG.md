# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Window and sidebar branding**: the UI window title, tray tooltip, and sidebar header now use the project name **`try-working-hard`** instead of the old generic nudge phrase (e.g. Chinese **滑鼠定時微動** / English **Mouse nudge**). The optional subtitle line stays hidden unless `app_subtitle` is set in strings.

### Added

- **Natural activity mode** (Home → Control): choose **Pattern** (line / circle / square, unchanged) or **Natural** for irregular micro-moves within the nudge radius, with optional **low-rate** left click and wheel scroll after the cursor is restored. Preferences: `activity_style` (`pattern` | `natural`), `natural_rare_click`, `natural_rare_scroll`. Analytics path pie includes **Natural** as a fourth slice.
- **PySide6 UI workspace**: introduced a modern multi-page desktop shell with `Dashboard`, `Tasks`, and `Settings` views, plus supporting window bootstrapping in `main.py`.
- **Reusable UI components**: added `StatCard`, `CustomTable`, `SidebarButton`, `Toast`, and `OneTimeReminderDialog` to support richer dashboards and in-app feedback.
- **Page-level structure**: added dedicated page modules under `views/` and icon assets under `assets/icons/` for sidebar navigation and page framing.

### Changed

- **Application state layer**: expanded preferences and view-model wiring (`ui/preferences_store.py`, `ui/view_model.py`) for the new workspace layout and settings flow.
- **Styling system**: added and tuned `styles/styles.qss` for a consistent modern visual system across cards, sidebar navigation, and page sections.
- **Project metadata**: refined `pyproject.toml` package metadata and English project description for publishing consistency.
- **Documentation coverage**: refreshed `README.md`, `README.zh-TW.md`, and this changelog to better capture feature behavior and recent UI/settings updates.

### Removed

- **Repository lockfile tracking**: removed tracked `uv.lock` from version control and updated `.gitignore` so lockfile churn does not pollute release history.

## [1.2.0] - 2026-04-28

### Added

- **Analytics** (sidebar): Matplotlib charts for nudge counts (today by hour or last 7 days), **scheduled uptime** per day (minutes, last 14 days), and **path usage** pie (totals). Aggregates persist as **`analytics.json`** next to `config.json` (same folder as the app config, e.g. `%APPDATA%\try-working-hard\` on Windows). The Home activity log is unchanged.
- **Schedule window** (Mon–Fri, local time): optional **work-hours** band (default **09:00–18:00**) so nudges run only inside that window; **evenings and weekends** stay paused with a **schedule paused** state until the next window. Config: `schedule_window`, **`schedule_window_start_text`** / **`schedule_window_end_text`** (**HH:MM**, 24h). When enabled, **Home** shows a short line under the status strip with the active window (or a fix-times prompt if invalid).
- **Windows idle-aware scheduling**: waits use **`GetLastInputInfo`** so a nudge runs only after the **interval** has passed with **no keyboard or mouse input**; repeated nudges while idle still require a full interval between events (synthetic cursor motion may not count as user input).
- **Interval jitter (± sec)** on **Home → Control**: optional uniform randomization of the **idle-required** interval (`interval ± N` seconds, clamped); config **`interval_jitter_text`** (0–3600; `0` disables).
- **Dark / light UI**: **Settings → Appearance** toggles **Dark** or **Light**; stored as **`ui_theme`** in `config.json` (`"dark"` | `"light"`, default **`"light"`**). Dark uses a GitHub-style dark surface; light keeps **`#F9FAFB`** / card layout with the **blue** theme family.
- **Windows**: **Start with Windows** (Settings, when `pystray` is available) — optional **`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`** entry passing **`--start-in-tray`** so the app starts at sign-in in the tray.
- **Home → Control**: quick interval buttons **30s / 1m / 5m / 10m** next to the interval field (set unit and value together).
- **CLI**: **`python -m mouse_jiggler --start-in-tray`** (and **`try-working-hard --start-in-tray`**) to launch with the main window hidden and only the system tray (pystray required).
- **Cursor skill** **`release-tag-pr-to-master`**: **PEP 621 / build output** notes — `pyproject.toml` **`[project] version`** drives **`dist/`** sdist and wheel names; optional **`__version__`** should match the release.

### Changed

- **Settings → Work hours**: the **schedule window** toggle moved from **Home → Control** into **Settings** (above tray / autostart), fixing a **grid overlap** that could hide parts of **path speed** when both were visible.
- **Settings layout**: same **sidebar page shell** as **Analytics** (one **bordered card**); the **form body** is a **`CTkScrollableFrame`** so long option lists scroll when the window is short; the **Settings** title stays **pinned** at the top of the card.
- **GUI (CustomTkinter)**: **light** mode uses **`appearance_mode` light** with built-in **blue**; **dark** uses **`appearance_mode` dark** with **dark-blue** and a Pro Dark–inspired palette. Titles use a larger **bold** scale; radii stay **12–16** px.
- **Window**: main GUI opens **maximized** on startup (Windows: **`wm state zoomed`**; elsewhere **`-zoomed`** when supported). Maximize is **re-applied** after the first layout tick and after the first-run **intro** dialog so CustomTkinter / modals do not leave the window at default size.
- **Navigation**: removed the duplicate **Home / Settings / Analytics** segmented control above page content — the **sidebar** is the only navigation for those sections.
- **Home status**: **schedule** and run state in a **bordered strip** at the **top** with a **colored indicator** and tint (muted when stopped, green while counting down, amber reserved for a future active-motion phase). The **progress bar** was removed in favor of status text.
- **Home → Control**: control card is **scrollable**; field order is **interval** (with quick presets) → **interval jitter** → **nudge size** → **path speed** → **motion path**.
- **Motion path**: **line**, **circle**, or **square**; **path speed** (1–10) scales trace speed. Config: **`motion_pattern`**, **`path_speed_text`**. Older `config.json` files that used **`motion_burst_text`** are ignored for path speed until the user saves again.
- **Keyboard**: **Enter** starts and **Esc** stops the schedule under the same rules as **F5** / **Shift+F5** on **Home → Control**, only while the **main window is visible** (not when closed to the **system tray**).
- **Settings → Open config file**: opens the JSON preferences in the system default application (creates it from current in-memory settings first if missing). Without `os.startfile`, the app shows the resolved path in a message box.
- **App icon**: shared **`mouse_jiggler/assets/app_icon.png`** for the main window (`iconphoto`), system tray, and the Windows **`.exe`** via **`packaging/app.ico`** in the PyInstaller spec. Regenerate with **`uv run python packaging/generate_icons.py`**.
- **Cursor**: **`.cursor/commands/pr-to-develop.md`** — removed the **Before you submit** block; **`open-pr-to-develop`** skill preconditions updated to match.
- **Cursor skill** **`dev-branch-auto`**: **Git worktree under `D:\projects\worktree` is mandatory** — branches are created with **`git worktree add`** only; default base **`origin/develop`**; topic branch must **upstream-track `origin/<branch>`** (not `develop`), including first push with **`git push -u`** / **`git branch -u`** and checking **`@{upstream}`**.
- **`docs/ACCESSIBILITY.md`**: keyboard and reduced-motion notes updated for the Home status line (progress bar removed).

### Fixed

- **Analytics (Matplotlib)**: empty-state and axis labels no longer render as **garbled or tofu blocks** when the UI language is **Chinese** — plots use a **CJK-capable** system font on Windows (**Microsoft JhengHei** / **YaHei** via explicit **`FontProperties`**) and disable problematic Unicode minus handling.
- **`scripts/open-pr-to-develop.ps1`**: **push** when upstream tracks the base branch.

## [1.1.0] - 2026-04-27

### Added

- **Interval units**: wait between nudges can be set in **minutes** or **seconds** (decimals allowed, minimum **0.1** minute equivalent); config, localization, and tests updated.
- **Nudge logic**: **`nudge_logic`** helpers and tests for ETA / timing; foundation for later idle-based scheduling in v1.2.0.
- **Per-interval motion**: **active motion** duration and trajectory wiring (evolved in later releases into **line / circle / square** paths and **path speed**).
- **Developer workflow**: **`.cursor/rules`** (changelog+README on completion, English-only project docs), **`.cursor/skills/dev-branch-auto`**, **`open-pr-to-develop`**, **`release-tag-pr-to-master`**; **`.cursor/commands/pr-to-develop.md`**; **`scripts/open-pr-to-develop.ps1`** for pushing and opening GitHub PRs to **`develop`**.

### Changed

- **GUI**: large **CustomTkinter** refresh — sidebar, Home, Settings, and layout updates toward the v1.2.0 shell.
- **Localization** (`strings`), **local config**, **Win32 mouse** helpers, **cursor nudge** implementation, and **tests** expanded for new interval and motion behavior.

### Notes

- Package version **`1.1.0`** in `pyproject.toml` for this release line.

## [1.0.0] - 2026-04-27

### Added

- **Windows-only** mouse nudge: periodically moves the cursor horizontally via the Win32 API (`GetCursorPos` / `SetCursorPos`) and restores it, for lawful personal use (e.g. keeping the session awake during a presentation or reading).
- **GUI** (CustomTkinter): dark theme, sidebar, tab switching, progress bar; countdown and progress toward the next nudge while running.
- **Bilingual UI**: Traditional Chinese and English; **default** language is English (new installs / missing config).
- **Tunable settings**: interval in minutes (decimals allowed, minimum 0.1), horizontal nudge size in pixels (0–500; 0 skips cursor movement for that tick).
- **System tray** (pystray + Pillow): optional “minimize to tray on close” so the schedule keeps running in the background; tray icon menu to show the window or exit (labels follow the UI language).
- **CLI entry points**: `try-working-hard` and `python -m mouse_jiggler`.
- **License**: MIT (see `LICENSE` in the repository root).
- **Keyboard & accessibility**: F1 help; F2–F4 page navigation; F5 / Shift+F5 start/stop on Home → Control; F6 toggles Control/Log; Tab through focusable controls; clickable labels to focus interval/nudge fields; `takefocus` tuned for CustomTkinter widgets. See `docs/ACCESSIBILITY.md` for screen-reader limitations (canvas-drawn UI).
- **Windows distribution**: optional `build` extra with **PyInstaller**; `packaging/try-working-hard.spec` produces `dist/try-working-hard.exe` (one-file, windowed). Documented in `docs/WINDOWS-BUILD.md` (includes GitHub Actions and brief mention of Briefcase).
- **GitHub Release workflow** (`.github/workflows/release.yml`): on `v*` tags, run tests, build the `.exe`, attach to the release with generated notes.
- **Local preferences** (`config.json` under `%APPDATA%\try-working-hard\` on Windows, or `~/.try-working-hard/` if `APPDATA` is unset): language, interval and nudge fields, “close to tray” switch, and intro flag; debounced save on change plus save on exit.
- **First-run welcome dialog** (system message box): usage and compliance summary; shown once per install unless the config file is removed or `intro_acknowledged` is reset. Existing configs without that key are treated as already acknowledged (no popup on upgrade).

### Notes

- First **stable** release; package version `1.0.0` in `pyproject.toml`. `__version__` is exposed from `mouse_jiggler` via `importlib.metadata` when the package is installed.
