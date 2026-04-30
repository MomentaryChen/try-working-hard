# Windows: standalone `.exe` (no Python on the target PC)

The app is a normal Python package; end users can run it with **uv** or `pip` (see the main [README](../README.md)). This document explains how to produce a **single file** you can hand to people who do not have Python installed.

## PyInstaller (recommended in this repository)

The spec at [`packaging/try-working-hard.spec`](../packaging/try-working-hard.spec) builds a **one-file, windowed** (no console) executable: `dist/try-working-hard.exe`.

From the project root, with [uv](https://docs.astral.sh/uv/) and the optional `build` extra:

```powershell
uv sync --group dev --extra build
uv run pyinstaller packaging/try-working-hard.spec
```

Or use the helper script (same result; `pwsh -File build.ps1 -Clean` removes `build/` and `dist/` first):

```powershell
pwsh -File build.ps1
```

The output is `dist/try-working-hard.exe`. You can share that file as-is, or let **GitHub Actions** build and attach it when you push a version tag (see [`.github/workflows/release.yml`](../.github/workflows/release.yml)).

### What the spec does

- Entry point: `mouse_jiggler/__main__.py`
- Collects `customtkinter` and `pystray` resources via PyInstaller hooks
- Collects `mouse_jiggler` data files (e.g. optional under `mouse_jiggler/assets/`)
- **Windowed** mode (no extra console window)
- **File icon**: embeds [`packaging/app.ico`](../packaging/app.ico) when that file exists (Explorer / taskbar shortcut icon for the `.exe`). To change the artwork, edit [`packaging/generate_icons.py`](../packaging/generate_icons.py) or replace the generated PNG/ICO, then from the repo root run:
  ```powershell
  uv run python packaging/generate_icons.py
  uv run pyinstaller packaging/try-working-hard.spec
  ```

### One-folder instead of one-file

For faster startup and easier AV debugging, you can generate a **folder** build by adjusting the `EXE` / `COLLECT` layout in a copy of the spec; see [PyInstaller — Spec files](https://pyinstaller.org/en/stable/spec-files.html). This repo’s release workflow only ships the **one-file** artifact.

### SmartScreen / antivirus

Unsigned Windows executables are sometimes flagged by **SmartScreen** or heuristics. Code signing and reputation over time help; the project does not provide signing. Users may need to use “Run anyway” or an enterprise allowlist.

### Portable `.exe` vs Inno Setup (`*-setup-*.exe`) and in-app updates

Each tagged release attaches:

- **`try-working-hard-vX.Y.Z.exe`** — PyInstaller **one-file** build. Good for copying to a folder or USB with no installer.
- **`try-working-hard-setup-vX.Y.Z.exe`** — **Inno Setup** installer produced from [`packaging/try-working-hard.iss`](../packaging/try-working-hard.iss).

The in-app updater (`mouse_jiggler/updater.py`, used from Settings and the update banner) **selects the installer asset** (names containing `setup` or `installer` are preferred when several `.exe` files are on the same release). It downloads that file, verifies **SHA256** against the optional checksums asset when the checksum file lists the same filename, then launches the installer. **That end-to-end “download and run the new installer” behavior is the supported automatic upgrade path for users who installed with the `*-setup-*.exe` build.** Portable-only users can still check for updates, but the offered file is the **installer**—run it to move to an installed layout, or upgrade the portable app by downloading a newer `try-working-hard-v*.exe` manually from GitHub **Assets**.

### Optional: console build (debugging)

To see stderr when something fails at launch, add a second spec (or one-off command) with `console=True` in the `EXE(…)` call so a terminal stays attached. The default published build stays **windowed** for a cleaner end-user experience.

## GitHub Action release

1. Update the version in `pyproject.toml` and the date in `CHANGELOG.md` (if not already).
2. Commit, then tag and push, for example:
   ```powershell
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. The **Release** workflow builds `try-working-hard.exe`, renames it to `try-working-hard-vX.Y.Z.exe`, then also builds an Inno Setup installer `try-working-hard-setup-vX.Y.Z.exe`. Both files plus `try-working-hard-vX.Y.Z-checksums.txt` are attached to the GitHub **Release**.

## Briefcase and other toolchains

[Beeware Briefcase](https://briefcase.readthedocs.io/) packages Python apps (often with a **Toga** or other native UI) into installers or platform-specific bundles. It is a valid choice for *new* projects or when you add a second UI layer. This codebase targets **CustomTkinter + PyInstaller**; Briefcase is **not** wired in the repo, but you can use it in parallel if you maintain a separate entry point and metadata—see the Briefcase documentation for Windows packaging.

Nuitka, cx_Freeze, and other freezers follow similar ideas (bundle interpreter + dependencies). The trade-offs (size, cold start, AV) are the same: test on a clean Windows VM without Python.
