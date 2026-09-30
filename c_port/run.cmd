@echo off
setlocal
cd /d "%~dp0.."
if not exist c_port\build\haunted_native.exe call c_port\build.cmd
if errorlevel 1 exit /b %errorlevel%
if not exist c_port\data\water\scene.hfc (
  echo Exporting the Python reference scene once. This may take several minutes.
  python c_port\export_scene.py --frames 120
  if errorlevel 1 exit /b 1
)
c_port\build\haunted_native.exe %*
