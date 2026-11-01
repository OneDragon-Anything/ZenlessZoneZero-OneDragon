param(
    [string]$ReportDir = '.install/charge-plan-validation'
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'src'

# 从仓库根目录运行；测试代码必须来自配套测试仓，不回退到上游 main。
if (-not (Test-Path -LiteralPath 'src/zzz_od/application/charge_plan')) {
    throw '请从主仓根目录运行验证脚本'
}
$testRoot = 'zzz-od-test/test/zzz_od'
$testFiles = @(
    "$testRoot/application/charge_plan/test_charge_plan_app_switch_team.py",
    "$testRoot/application/charge_plan/test_charge_plan_config.py",
    "$testRoot/application/charge_plan/test_charge_plan_switch_team_persistence.py",
    "$testRoot/application/charge_plan/test_charge_plan_timeout_config.py",
    "$testRoot/application/charge_plan/test_charge_plan_timeout_preset_ui.py",
    "$testRoot/application/charge_plan/charge_plan_app/test_parse_battery_charge_ocr.py",
    "$testRoot/operation/compendium/test_charge_plan_auto_switch_team.py",
    "$testRoot/operation/compendium/test_charge_plan_retry_flow.py"
)
foreach ($testFile in $testFiles) {
    if (-not (Test-Path -LiteralPath $testFile)) { throw "缺少配套测试：$testFile" }
}
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$mainSha = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw '无法读取主仓提交' }
$testSha = git -C zzz-od-test rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw '无法读取测试仓提交' }
$pythonVersion = uv run --group dev --no-sync python --version
if ($LASTEXITCODE -ne 0) { throw '无法运行开发环境 Python' }
@{
    main_sha = $mainSha
    test_sha = $testSha
    python = $pythonVersion
    test_files = $testFiles
    excluded = @('test_exchange_ether_battery_is_dispatched_in_transport: 需要完整游戏/OCR context，与换队变更无关')
    scope = '换队及相关配置/解析回归；多帧流程模拟视觉结果，不替代实机识别验收'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$ReportDir/versions.json" -Encoding utf8

$sourceFiles = @(
    'src/zzz_od/application/charge_plan/charge_plan_app.py',
    'src/zzz_od/application/charge_plan/charge_plan_config.py',
    'src/zzz_od/application/charge_plan/charge_plan_const.py',
    'src/zzz_od/backend/config_router.py',
    'src/zzz_od/gui/view/one_dragon/charge_plan_interface.py',
    'src/zzz_od/operation/compendium/area_patrol.py',
    'src/zzz_od/operation/compendium/combat_simulation.py',
    'src/zzz_od/operation/compendium/expert_challenge.py',
    'src/zzz_od/operation/compendium/notorious_hunt.py'
)
# OCR 解析文件是未修改的上游回归；不对它做额外风格检查。
$changedTests = $testFiles | Where-Object { $_ -notlike '*/test_parse_battery_charge_ocr.py' }
uv run --group dev --no-sync ruff check @sourceFiles @changedTests
if ($LASTEXITCODE -ne 0) { throw 'Ruff 检查失败' }

uv run --group dev --no-sync pytest @testFiles -q `
    -k 'not test_exchange_ether_battery_is_dispatched_in_transport' `
    -p no:cacheprovider --basetemp="$ReportDir/tmp" --junitxml="$ReportDir/junit.xml"
if ($LASTEXITCODE -ne 0) { throw '回归测试失败' }
[xml]$junit = Get-Content -LiteralPath "$ReportDir/junit.xml" -Raw -Encoding utf8
$suites = @($junit.testsuites.testsuite)
$total = ($suites | Measure-Object -Property tests -Sum).Sum
$skipped = ($suites | Measure-Object -Property skipped -Sum).Sum
if ($total -le 0 -or $skipped -ne 0) { throw '核心回归未执行或存在跳过项' }
Write-Host "回归完成：$total 项，0 项跳过；主仓 $mainSha；测试仓 $testSha"
