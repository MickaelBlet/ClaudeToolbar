@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building ClaudeSystemTrayUsage.exe...
python build.py

echo.
if exist dist\ClaudeSystemTrayUsage.exe (
    echo Build successful! Executable is at: dist\ClaudeSystemTrayUsage.exe
) else (
    echo Build failed. Check the output above for errors.
)

dist\ClaudeSystemTrayUsage.exe
