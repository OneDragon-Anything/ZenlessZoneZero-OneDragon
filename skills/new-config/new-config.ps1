# new-config.ps1
# ZenlessZoneZero-OneDragon 新建配置构建脚本
# 设置 PYTHONPATH 到 src 目录，运行 build_utils.py 构建合并 YAML

param(
    [switch]$DryRun
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SrcPath = Join-Path $ProjectRoot "src"

if (-not (Test-Path $SrcPath)) {
    Write-Error "src 目录不存在: $SrcPath"
    exit 1
}

$BuildScript = Join-Path $ProjectRoot "src\zzz_od\auto_battle\build_utils.py"
if (-not (Test-Path $BuildScript)) {
    Write-Error "build_utils.py 不存在: $BuildScript"
    exit 1
}

$Env:PYTHONPATH = $SrcPath

Write-Host "项目根目录: $ProjectRoot"
Write-Host "PYTHONPATH:   $Env:PYTHONPATH"
Write-Host "构建脚本:     $BuildScript"

if ($DryRun) {
    Write-Host ""
    Write-Host "DryRun 模式 - 跳过执行"
    exit 0
}

Write-Host ""
Write-Host "开始构建 merged.yml..."
uv run python $BuildScript

if ($LASTEXITCODE -ne 0) {
    Write-Error "构建失败，退出码: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "构建完成！merged.yml 文件已更新。"