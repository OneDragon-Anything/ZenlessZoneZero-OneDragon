param([switch]$SkipArchive)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$locator = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path -LiteralPath $locator) {
    $builder = & $locator -latest -products '*' -requires Microsoft.Component.MSBuild -find 'MSBuild\**\Bin\MSBuild.exe' | Select-Object -First 1
}
if (-not $builder) {
    $command = Get-Command MSBuild.exe -ErrorAction SilentlyContinue
    if ($command) { $builder = $command.Source }
}
if (-not $builder) { throw '未找到 Visual Studio MSBuild。请安装 .NET 桌面开发与 .NET Framework 4.7.2 targeting pack。' }

$launcherProject = Join-Path $projectRoot 'OneDragonLauncherWpf\OneDragonLauncherWpf.csproj'
$packageDirectory = Join-Path $projectRoot 'packages'
[xml]$packageManifest = Get-Content -LiteralPath (Join-Path $projectRoot 'OneDragonLauncherWpf\packages.config')
$missingPackages = @($packageManifest.packages.package | Where-Object {
    -not (Test-Path -LiteralPath (Join-Path $packageDirectory ($_.id + '.' + $_.version)))
})
if ($missingPackages.Count -gt 0) {
    & $builder $launcherProject /t:Restore /p:RestorePackagesConfig=true "/p:RestoreRepositoryPath=$packageDirectory" /nologo /v:minimal
    if ($LASTEXITCODE -ne 0) { throw 'NuGet 程序包还原失败。' }
}

& $builder $launcherProject /t:Build /p:Configuration=Release /p:Platform=x64 /nologo /v:minimal
if ($LASTEXITCODE -ne 0) { throw 'Release 构建失败。' }

$releaseDirectory = Join-Path $projectRoot 'OneDragonLauncherWpf\bin\x64\Release'
$artifactDirectory = Join-Path $projectRoot 'artifacts'
New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null
$configurationPath = Join-Path $releaseDirectory 'OneDragon-Launcher.exe.config'
if (Test-Path -LiteralPath $configurationPath) {
    [xml]$configuration = Get-Content -LiteralPath $configurationPath
    $externalSettings = @($configuration.configuration.ChildNodes | Where-Object {
        $_.NodeType -eq [Xml.XmlNodeType]::Element -and $_.Name -ne 'startup'
    })
    if ($externalSettings.Count -gt 0) {
        throw '生成的 exe.config 含运行时设置或绑定重定向，不能静默省略。请先验证这些配置的单文件兼容性。'
    }
}
$singleExecutable = Join-Path $artifactDirectory 'OneDragon-Launcher.exe'
Copy-Item -LiteralPath (Join-Path $releaseDirectory 'OneDragon-Launcher.exe') -Destination $singleExecutable -Force
Write-Host ("单文件: {0} ({1:N2} MiB)" -f $singleExecutable, ((Get-Item -LiteralPath $singleExecutable).Length / 1MB))
if (-not $SkipArchive) {
    $archivePath = Join-Path $artifactDirectory 'OneDragon-Launcher-Windows.zip'
    Compress-Archive -LiteralPath $singleExecutable -DestinationPath $archivePath -Force
    Write-Host "已生成: $archivePath"
}
