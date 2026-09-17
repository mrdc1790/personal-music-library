@echo off
pushd "%~dp0"
python library_demo.py
echo.
echo This example does not connect to Spotify or change your music.
pause
popd
