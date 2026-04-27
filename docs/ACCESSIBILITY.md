# Accessibility (CustomTkinter / Tk on Windows)

This app is **Windows-only** and uses **CustomTkinter** for most of the window. A few things are useful to know for keyboard users and for assistive technology.

## What we improved in code

- **Tab / Shift+Tab** can move between interactive controls; `takefocus` is enabled on buttons, entries, segmented controls, the tray switch, and log read-only text areas. The **status line** at the top of Home is display-only (not in the focus ring).
- **F1** opens a help dialog (standard `tkinter` messagebox) with **keyboard shortcuts** and a short **screen reader** note. The help text is localized with the app strings (Traditional Chinese / English).
- **F2 / F3 / F4** go to **Home, Settings, Analytics**.
- On **Home → Control** only: **F5** = **Start**, **Shift+F5** = **Stop** (if the action is available).
- **F6** toggles **Control / Log** on Home; if you are on another page, it switches to Home first.
- **Click the “Interval”, “Nudge (pixels)”, or “Active motion (sec)” labels** to move focus to the corresponding field (the label cursor becomes a hand where supported).

## Limitations of CustomTkinter with screen readers

CustomTkinter draws many widgets on an internal **canvas**, not always as separate native `HWND` controls. **Narrator**, **NVDA**, and **JAWS** may not announce every label or button the same way they would in a full Win32 or UWP app. In practice:

- The **window title** and the **F1** help **messagebox** use standard Windows UI and are the most reliable for announcements.
- **Error dialogs** from `messagebox` are also standard and screen-reader friendly.
- The **system tray** menu (pystray) depends on the host shell; use **Show / Quit** from the tray with care if your reader does not see it.

If you need **strong** ARIA/IA2 guarantees, a future version would need a different UI stack (e.g. native Win32/WPF) or a browser-based UI, which is not in scope for the current 1.0.0 line.

## Operating system and tools

- **OS Magnifier**, **high-contrast** themes, and **sticky keys** work as usual; they are independent of the app.
- For **reduced motion**, the countdown text is not tied to a system setting; you can **Stop** the schedule to halt cursor movement and timer updates.

## Reporting issues

If a specific reader + Windows version **combination** fails, open an issue with the reader name, version, and steps. Patches that improve **focus order** or **label–field association** (without a full UI rewrite) are welcome.
