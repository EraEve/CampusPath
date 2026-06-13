"""Smart Navigation (智慧导航) — Entry Point.

Launches the tkinter GUI application.
"""
import sys
import os

# Ensure the package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smart_navigation.main import main

if __name__ == "__main__":
    main()
