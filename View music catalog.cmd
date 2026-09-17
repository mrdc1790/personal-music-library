@echo off
pushd "%~dp0"
python view_catalog.py %*
if errorlevel 1 pause
popd
