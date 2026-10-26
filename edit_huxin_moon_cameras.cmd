@echo off
setlocal
cd /d "%~dp0"
set "HAUNTED_MUTE_AUDIO=1"
python huxin_moon_cinematographer.py %*
endlocal
