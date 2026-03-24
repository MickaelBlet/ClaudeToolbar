@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building ClaudeToolbar.exe...
python build.py

echo.
if exist dist\ClaudeToolbar.exe (
    echo Build successful! Executable is at: dist\ClaudeToolbar.exe
) else (
    echo Build failed. Check the output above for errors.
)
pause
