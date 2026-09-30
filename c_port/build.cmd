@echo off
setlocal
set "PATH=C:\raylib\w64devkit\bin;%PATH%"
cmake -S "%~dp0." -B "%~dp0build" -G "MinGW Makefiles" -DCMAKE_C_COMPILER=C:/raylib/w64devkit/bin/gcc.exe -DCMAKE_MAKE_PROGRAM=C:/raylib/w64devkit/bin/mingw32-make.exe -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b %errorlevel%
cmake --build "%~dp0build" --parallel 2
exit /b %errorlevel%
