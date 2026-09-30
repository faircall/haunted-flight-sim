param([string]$RaylibRoot = 'C:/raylib/raylib', [string]$Toolchain = 'C:/raylib/w64devkit/bin')
$ErrorActionPreference = 'Stop'
$env:PATH = "$Toolchain;$env:PATH"
cmake -S $PSScriptRoot -B "$PSScriptRoot/build" -G 'MinGW Makefiles' "-DCMAKE_C_COMPILER=$Toolchain/gcc.exe" "-DCMAKE_MAKE_PROGRAM=$Toolchain/mingw32-make.exe" "-DRAYLIB_ROOT=$RaylibRoot" -DCMAKE_BUILD_TYPE=Release
if ($LASTEXITCODE) { exit $LASTEXITCODE }
cmake --build "$PSScriptRoot/build" --parallel 2
exit $LASTEXITCODE
