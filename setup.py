#!/usr/bin/env python3
"""
Run this ONCE after setting up the Replit project.
It installs the Chromium browser needed for automation.
"""
import subprocess
import sys

print("Installing Python dependencies...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

print("\nInstalling Playwright Chromium browser...")
subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
subprocess.check_call([sys.executable, "-m", "playwright", "install-deps", "chromium"])

print("\n✅ Setup complete! You can now run: python app.py")
