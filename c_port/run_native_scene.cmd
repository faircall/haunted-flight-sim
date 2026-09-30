@echo off
setlocal
cd /d "%~dp0.."
if not exist c_port\build\haunted_native.exe call c_port\build.cmd
if errorlevel 1 exit /b %errorlevel%
if not exist c_port\data\water-native\scene.hfc (
  echo Exporting the reference with native scene stages enabled.
  python c_port\export_scene.py --native-scene --frames 240
  if errorlevel 1 exit /b 1
)
c_port\build\haunted_native.exe --scene c_port\data\water-native\scene.hfc %*
