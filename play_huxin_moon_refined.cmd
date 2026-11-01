@echo off
setlocal
cd /d "%~dp0"
set "HAUNTED_PLAYER_VARIANT=refined"
python huxin_moon_viewer.py %*
