# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **GUI (CustomTkinter)**: switched to a **light** appearance (`appearance_mode` **light** / built-in **blue** theme) with a **#F9FAFB** app surface, **#F3F4F6** sidebar, **#FFFFFF** content cards (1px **#E5E7EB** border), **#3B82F6** primary actions with white copy, and transparent **secondary** actions with gray text; titles use a larger **bold** type scale and radii in the **12–16** px range for a rounder layout.

- **Window**: the main **GUI** window opens **maximized** on startup (Windows: `wm state zoomed`; elsewhere `-zoomed` when supported). Restore or resize with the system window controls as usual.

- **Cursor command** `.cursor/commands/pr-to-develop.md`: added a **Before you submit** section describing how to confirm the branch has **no merge conflicts** with `origin/develop` before running `open-pr-to-develop.ps1`.

- **Main panel**: removed the duplicate **Home / Settings / Analytics** segmented control above the page content; **sidebar** is the only navigation for those sections.

- **Home status**: the schedule state is shown in a **bordered strip** with a **colored indicator** and tint (muted when stopped, green while counting down to the next nudge, amber during active motion).

- **Home**: runtime status and countdown moved to the **top** of the page (above the dashboard title) so they stay visible while adjusting controls or reading the log; the **progress bar** was removed in favor of the status text alone.

- **Cursor skill** `dev-branch-auto`: **Git worktree under `D:\projects\worktree` is now mandatory** when the skill runs—new branches are created with `git worktree add` only; the agent continues work from the new path instead of switching the main clone.

- **Cursor skill** `dev-branch-auto`: default base branch is now **`origin/develop`** (no implicit `main`/`master` fallback unless the user names another base).

- **docs/ACCESSIBILITY.md**: keyboard and reduced-motion notes updated for the Home status line (progress bar removed).

### Added

- **Keyboard**: **Enter** starts and **Esc** stops the schedule under the same rules as **F5** / **Shift+F5** on **Home → Control**, but only while the **main window is visible** (not when the window is closed to the **system tray**).

- **App branding icon**: shared `mouse_jiggler/assets/app_icon.png` for the main window (`iconphoto`), system tray, and the Windows `.exe` file icon via `packaging/app.ico` in the PyInstaller spec. Regenerate both from `packaging/generate_icons.py` (`uv run python packaging/generate_icons.py`).

- **Settings → Open config file**: button on the Settings page opens the JSON preferences file in the system default app (or creates it from the current in-memory settings first if it is missing). On systems without `os.startfile`, the app shows the resolved path in a message box.

- **Active motion (seconds)** on Home → Control: after each interval elapses, the app can keep nudging at a fixed cadence for that duration before the next idle wait; `0` keeps the previous behavior (one nudge per tick). Persisted in local config as `motion_burst_text`. If nudge size is `0`, the extra duration is skipped.

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
