"""Build script to create the standalone .exe using PyInstaller."""

import PyInstaller.__main__
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
sep = ";" if os.name == "nt" else ":"

PyInstaller.__main__.run([
    os.path.join(script_dir, "main.py"),
    "--name=ClaudeSystemTrayUsage",
    "--onefile",
    "--windowed",
    f"--icon={os.path.join(script_dir, 'assets', 'app_icon.ico')}",
    f"--add-data={os.path.join(script_dir, 'config.py')}{sep}.",
    f"--add-data={os.path.join(script_dir, 'claude_usage.py')}{sep}.",
    "--hidden-import=pystray._win32",
    "--hidden-import=curl_cffi",
    "--hidden-import=tkinter",
    "--distpath", os.path.join(script_dir, "dist"),
    "--workpath", os.path.join(script_dir, "build"),
    "--specpath", script_dir,
    "--noconfirm",
])
