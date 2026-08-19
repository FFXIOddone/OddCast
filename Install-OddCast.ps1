[CmdletBinding()]
param([string]$AshitaRoot)

$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $packageRoot 'oddcast'
$required = @(
    'LICENSE-LUASHITACAST-MIT', 'LICENSE-ODDCAST-GPL-3.0', 'README.md',
    'THIRD_PARTY_NOTICES.md', 'locales.lua', 'oddcast.lua', 'ui_skin.lua',
    'update_checker.lua', 'weakness_data.lua', 'weakness_data_manifest.json'
)

if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw 'The oddcast payload directory is missing. Extract the complete release ZIP first.'
}
$actual = @(Get-ChildItem -LiteralPath $source -File | Select-Object -ExpandProperty Name | Sort-Object)
$expected = @($required | Sort-Object)
if (Compare-Object $expected $actual) {
    throw 'The oddcast payload inventory is incomplete or contains unexpected files.'
}

if ([string]::IsNullOrWhiteSpace($AshitaRoot)) {
    $candidates = @((Join-Path $packageRoot 'Ashita'), 'C:\Games\CatsEyeXI\catseyexi-client\Ashita', 'C:\Ashita')
    $AshitaRoot = $candidates | Where-Object {
        Test-Path -LiteralPath (Join-Path $_ 'addons') -PathType Container
    } | Select-Object -First 1
}
if ([string]::IsNullOrWhiteSpace($AshitaRoot)) {
    throw 'Ashita was not found. Run Install-OddCast.cmd -AshitaRoot "C:\path\to\Ashita".'
}

$resolvedAshita = (Resolve-Path -LiteralPath $AshitaRoot).Path
$addons = Join-Path $resolvedAshita 'addons'
if (-not (Test-Path -LiteralPath $addons -PathType Container)) {
    throw "The selected Ashita root has no addons directory: $resolvedAshita"
}
$destination = Join-Path $addons 'oddcast'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stage = Join-Path $addons ('.oddcast-stage-' + $stamp)
$backup = Join-Path $addons ('oddcast-backup-' + $stamp)
if ((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $backup)) {
    throw 'A staging or backup path already exists for this timestamp; wait one second and retry.'
}

New-Item -ItemType Directory -Path $stage | Out-Null
try {
    foreach ($name in $required) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $stage $name)
        $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $source $name)).Hash
        $stageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $stage $name)).Hash
        if ($sourceHash -ne $stageHash) { throw "Staged hash mismatch: $name" }
    }
    if (Test-Path -LiteralPath $destination) { Move-Item -LiteralPath $destination -Destination $backup }
    Move-Item -LiteralPath $stage -Destination $destination
    foreach ($name in $required) {
        $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $source $name)).Hash
        $installedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $destination $name)).Hash
        if ($sourceHash -ne $installedHash) { throw "Installed hash mismatch: $name" }
    }
} catch {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    if (-not (Test-Path -LiteralPath $destination) -and (Test-Path -LiteralPath $backup)) {
        Move-Item -LiteralPath $backup -Destination $destination
    }
    throw
}

Write-Host "Installed OddCast to: $destination"
if (Test-Path -LiteralPath $backup) { Write-Host "Previous install backed up to: $backup" }
Write-Host 'In Ashita, run: /addon load oddcast'
