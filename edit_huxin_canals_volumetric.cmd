@echo off
setlocal
cd /d "%~dp0"
set "HAUNTED_MUTE_AUDIO=1"
python huxin_canals_editor.py --direction art/temple/huxin_canals/direction-volumetric.json %*
endlocal
