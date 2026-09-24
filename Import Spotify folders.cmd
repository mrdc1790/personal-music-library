@echo off
cd /d "%~dp0"
python folder_tree.py --latest-run
if errorlevel 1 goto done
python preview_audit.py --open
:done
pause
