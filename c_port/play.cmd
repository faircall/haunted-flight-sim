@echo off
setlocal
cd /d "%~dp0.."
if not exist c_port\build\haunted_game.exe (
  echo Run python c_port\build_game.py once before playing the compiled C game.
  exit /b 1
)
c_port\build\haunted_game.exe %*
