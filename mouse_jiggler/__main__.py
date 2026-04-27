"""Allow ``python -m mouse_jiggler`` and PyInstaller (which runs this file as a plain script, not a package)."""

from mouse_jiggler.app import main

if __name__ == "__main__":
    main()
