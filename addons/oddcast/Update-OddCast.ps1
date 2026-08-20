[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CurrentVersion,
    [Parameter(Mandatory=$true)][string]$AddonPath,
    [Parameter(Mandatory=$true)][string]$ResultPath
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$apiUrl = 'https://api.github.com/repos/FFXIOddone/OddCast/releases/latest'
$resolvedAddon = (Resolve-Path -LiteralPath $AddonPath).Path
$addonsRoot = Split-Path -Parent $resolvedAddon
$ashitaRoot = Split-Path -Parent $addonsRoot
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('OddCast-update-' + [Guid]::NewGuid().ToString('N'))
$updaterMutex = [Threading.Mutex]::new($false, 'Local\OddCastUpdater')
$ownsMutex = $false

function Write-Result([string]$Status, [string]$Detail) {
    $safe = ($Detail -replace '[\r\n]+', ' ').Trim()
    [IO.File]::WriteAllText($ResultPath, "$Status|$safe", [Text.UTF8Encoding]::new($false))
}

try {
    $ownsMutex = $updaterMutex.WaitOne(0)
    if (-not $ownsMutex) { throw 'Another OddCast update is already running.' }
    if ($CurrentVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'The installed version is invalid.' }
    if ((Get-Item -LiteralPath $resolvedAddon -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'The OddCast addon directory cannot be a link or reparse point.'
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $headers = @{ Accept='application/vnd.github+json'; 'User-Agent'='OddCast-updater' }
    $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 15
    $version = [string]$release.tag_name -replace '^OddCast-v', '' -replace '^v', ''
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'The latest release has an invalid version.' }
    if ([version]$version -le [version]$CurrentVersion) {
        Write-Result 'current' $CurrentVersion
        exit 0
    }

    $archiveName = "OddCast-v$version.zip"
    $archiveAsset = @($release.assets | Where-Object { $_.name -ceq $archiveName })
    $checksumAsset = @($release.assets | Where-Object { $_.name -ceq 'SHA256SUMS.txt' })
    if ($archiveAsset.Count -ne 1 -or $checksumAsset.Count -ne 1) {
        throw 'The release does not contain the required archive and checksum assets.'
    }

    New-Item -ItemType Directory -Path $temporary | Out-Null
    $archive = Join-Path $temporary $archiveName
    $checksums = Join-Path $temporary 'SHA256SUMS.txt'
    Invoke-WebRequest -Uri $archiveAsset[0].browser_download_url -Headers $headers -OutFile $archive -TimeoutSec 30
    Invoke-WebRequest -Uri $checksumAsset[0].browser_download_url -Headers $headers -OutFile $checksums -TimeoutSec 15
    if ((Get-Item -LiteralPath $archive).Length -gt 2097152) { throw 'The release archive exceeds the size limit.' }

    $checksumLines = @(Get-Content -LiteralPath $checksums -Encoding ASCII)
    $match = @($checksumLines | Where-Object { $_ -match ('^[0-9a-fA-F]{64}\s{2}' + [regex]::Escape($archiveName) + '$') })
    if ($match.Count -ne 1) { throw 'The release checksum entry is missing or ambiguous.' }
    $expectedHash = ($match[0] -split '\s+')[0].ToUpperInvariant()
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash
    if ($actualHash -cne $expectedHash) { throw 'The release archive checksum does not match.' }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $entries = @($zip.Entries)
        if ($entries.Count -lt 3 -or $entries.Count -gt 32) { throw 'The release archive inventory is invalid.' }
        foreach ($entry in $entries) {
            if ($entry.FullName -match '(^|/)\.\.?(/|$)|\\|^[A-Za-z]:' -or $entry.Length -gt 2097152) {
                throw "The release contains an unsafe archive member: $($entry.FullName)"
            }
        }
    } finally {
        $zip.Dispose()
    }

    $expanded = Join-Path $temporary 'expanded'
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $expanded)
    $installer = Join-Path $expanded 'Install-OddCast.ps1'
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'The release installer is missing.' }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -AshitaRoot $ashitaRoot
    if ($LASTEXITCODE -ne 0) { throw "The release installer exited with code $LASTEXITCODE." }
    Write-Result 'success' $version
} catch {
    try { Write-Result 'error' $_.Exception.Message } catch {}
    exit 1
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
    if ($ownsMutex) { $updaterMutex.ReleaseMutex() }
    $updaterMutex.Dispose()
}
