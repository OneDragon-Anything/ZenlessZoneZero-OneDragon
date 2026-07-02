# compile-po.ps1
# 编译 PO 文件（多语言翻译）
param(
    [switch]$DryRun
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SrcPath = Join-Path $ProjectRoot "src"
$ScriptPath = Join-Path $ProjectRoot "src\one_dragon\devtools\compile_po.py"

if (-not (Test-Path $SrcPath)) {
    Write-Error "src 目录不存在: $SrcPath"
    exit 1
}

if (-not (Test-Path $ScriptPath)) {
    Write-Error "compile_po.py 不存在: $ScriptPath"
    exit 1
}

$Env:PYTHONPATH = $SrcPath

Write-Host "项目根目录: $ProjectRoot"
Write-Host "PYTHONPATH:  $Env:PYTHONPATH"
Write-Host "脚本:        $ScriptPath"

if ($DryRun) {
    exit 0
}

uv run python $ScriptPath

if ($LASTEXITCODE -ne 0) {
    Write-Error "编译失败，退出码: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "PO 编译完成"