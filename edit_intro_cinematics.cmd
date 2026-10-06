@echo off
setlocal
cd /d "%~dp0"
python moonlit_water_temple_3d.py --cinematics-editor %*
