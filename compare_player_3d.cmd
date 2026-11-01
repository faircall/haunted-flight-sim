@echo off
setlocal
cd /d "%~dp0"
set "HAUNTED_MUTE_AUDIO=1"
python compare_player_3d.py %*
