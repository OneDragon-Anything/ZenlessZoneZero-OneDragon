# generate-manifest.ps1
# 生成模块清单文件（merged.yml 的模块注册）
param(
    [switch]$DryRun
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SrcPath = Join-Path $ProjectRoot "src"
$ScriptPath = Join-Path $ProjectRoot "deploy\generate_module_manifest.py"

if (-not (Test-Path $SrcPath)) {
    Write-Error "src 目录不存在: $SrcPath"
    exit 1
}

if (-not (Test-Path $ScriptPath)) {
    Write-Error "generate_module_manifest.py 不存在: $ScriptPath"
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
    Write-Error "生成失败，退出码: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "模块清单生成完成"