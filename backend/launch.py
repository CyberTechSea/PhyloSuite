"""
PhyloSuite Launcher
Entry point for the standalone executable.
Opens the browser automatically after the server starts.
"""

import os
import sys
import time
import threading
import webbrowser
from pathlib import Path

# ── Fix paths for PyInstaller bundle ───────────────────────
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR  = BASE_DIR
else:
    # Running as script
    BASE_DIR = Path(__file__).parent
    APP_DIR  = BASE_DIR

# Add backend to Python path
sys.path.insert(0, str(APP_DIR))

HOST = "127.0.0.1"
PORT = 5000


def open_browser():
    """Wait for server to start, then open browser"""
    time.sleep(2.5)
    url = f"http://{HOST}:{PORT}"
    print(f"  Opening browser → {url}")
    webbrowser.open(url)


def main():
    print("=" * 50)
    print("  PhyloSuite v1.0")
    print("  Phylogenetic Analysis Pipeline")
    print("=" * 50)
    print(f"  Server starting on http://{HOST}:{PORT}")
    print("  Press Ctrl+C to quit")
    print()

    # Launch browser in background
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    # Start Flask
    from app import create_app
    app = create_app()

    try:
        app.run(
            host=HOST,
            port=PORT,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\n  PhyloSuite stopped.")


if __name__ == "__main__":
    main()
