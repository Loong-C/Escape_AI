$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$buildPath = Join-Path $repoRoot "build\cpp"
$sourcePath = Join-Path $repoRoot "cpp"
$modulePath = Join-Path $repoRoot "src\escape_ai"
$pybindPath = & $pythonPath -m pybind11 --cmakedir

cmake -S $sourcePath -B $buildPath -G "Visual Studio 17 2022" -A x64 `
    -DPython3_EXECUTABLE="$pythonPath" `
    -Dpybind11_DIR="$pybindPath" `
    -DESCAPE_AI_PYTHON_OUTPUT_DIRECTORY="$modulePath"
cmake --build $buildPath --config Release --parallel
ctest --test-dir $buildPath -C Release --output-on-failure

