<#
.SYNOPSIS
    Installs VoiceType: creates its virtual environment, installs the
    dependencies, and registers it to start when you sign in.

.DESCRIPTION
    Run this once. It is safe to run again -- it reuses an existing
    environment and just refreshes the shortcuts.

    This script works two ways. Run from a copy of the project, it installs
    that copy. Piped straight into PowerShell, with no project on disk yet, it
    first downloads the project and then installs it. That is the one-command
    install in the README.

    The first run downloads PyTorch and the Whisper weights, so expect a few
    hundred megabytes and several minutes.

.PARAMETER InstallDir
    Where to put the project when bootstrapping. Defaults to
    %LOCALAPPDATA%\Programs\VoiceType. Ignored when the script is already
    running from a project folder.

.PARAMETER SetApiKey
    Prompts for an OpenAI API key and stores it outside the project, readable
    only by you. Needed only for the cloud backend.

.PARAMETER Uninstall
    Stops VoiceType and removes the shortcuts. Leaves the folder and the key.

.PARAMETER NoStart
    Set everything up but do not launch the app.

.PARAMETER NoAutostart
    Skip the Startup shortcut; VoiceType then only runs when you start it.

.PARAMETER Python
    Full path to a python.exe to build the environment from. Only needed if
    the script cannot find a suitable one by itself.

.EXAMPLE
    # One command, nothing cloned first:
    irm https://raw.githubusercontent.com/Maslitsa/VoiceType/main/install.ps1 | iex

.EXAMPLE
    # From a copy of the project:
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -SetApiKey
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
#>

[CmdletBinding()]
param(
    [switch]$Uninstall,
    [switch]$SetApiKey,
    [switch]$NoStart,
    [switch]$NoAutostart,
    [string]$Python,
    [string]$InstallDir
)

$ErrorActionPreference = 'Stop'

$RepoUrl = 'https://github.com/Maslitsa/VoiceType'

# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------
# `irm <url> | iex` executes this text with no file behind it, so
# $PSCommandPath is empty and there is no project folder to install from yet.
# In that case fetch the project first, then hand over to the copy on disk --
# which is the same script, now running the normal path below.
if (-not $PSCommandPath) {
    if (-not $InstallDir) {
        # Under Programs, not Documents or Desktop: no spaces to quote around,
        # and never inside a OneDrive-synced folder, which would try to sync
        # the multi-gigabyte environment created next to it.
        $InstallDir = Join-Path $env:LOCALAPPDATA 'Programs\VoiceType'
    }

    Write-Host ''
    Write-Host '  VoiceType' -ForegroundColor Cyan
    Write-Host "  installing into $InstallDir"
    Write-Host ''

    $parent = Split-Path -Parent $InstallDir
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    $hasGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
    if (Test-Path (Join-Path $InstallDir '.git')) {
        Write-Host '==> Updating the existing copy' -ForegroundColor Cyan
        & git -C $InstallDir pull --ff-only
        if ($LASTEXITCODE -ne 0) { throw 'git pull failed. Delete the folder and try again.' }
    } elseif ($hasGit -and -not (Test-Path $InstallDir)) {
        Write-Host '==> Cloning' -ForegroundColor Cyan
        & git clone --depth 1 "$RepoUrl.git" $InstallDir
        if ($LASTEXITCODE -ne 0) { throw 'git clone failed.' }
    } else {
        # No git, or a non-git folder is already there. Take the ZIP.
        Write-Host '==> Downloading' -ForegroundColor Cyan
        $stamp = [Guid]::NewGuid().ToString('N').Substring(0, 8)
        $zip = Join-Path $env:TEMP "VoiceType-$stamp.zip"
        $tmp = Join-Path $env:TEMP "VoiceType-$stamp"
        try {
            $ProgressPreference = 'SilentlyContinue'   # the bar makes this slow
            Invoke-WebRequest -Uri "$RepoUrl/archive/refs/heads/main.zip" `
                -OutFile $zip -UseBasicParsing
            Expand-Archive -Path $zip -DestinationPath $tmp -Force
            $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
            if (-not $inner) { throw 'The downloaded archive was empty.' }
            if (Test-Path $InstallDir) {
                # Keep config.json and logs across a reinstall.
                Get-ChildItem $inner.FullName -Force | ForEach-Object {
                    Copy-Item $_.FullName -Destination $InstallDir -Recurse -Force
                }
            } else {
                Move-Item $inner.FullName $InstallDir
            }
        } finally {
            Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $installer = Join-Path $InstallDir 'install.ps1'
    if (-not (Test-Path $installer)) {
        throw "Download did not produce an install.ps1 in $InstallDir."
    }

    # Pass along anything that was asked for, minus InstallDir which has now
    # done its job.
    $forward = @()
    foreach ($name in $PSBoundParameters.Keys) {
        if ($name -eq 'InstallDir') { continue }
        $value = $PSBoundParameters[$name]
        if ($value -is [System.Management.Automation.SwitchParameter]) {
            if ($value.IsPresent) { $forward += "-$name" }
        } else {
            $forward += "-$name"
            $forward += [string]$value
        }
    }

    # A child process with an explicit policy, because the caller's execution
    # policy may well forbid running a .ps1 from disk even though piping one
    # into the shell was allowed.
    & powershell -NoProfile -ExecutionPolicy Bypass -File $installer @forward
    exit $LASTEXITCODE
}

$Root       = Split-Path -Parent $PSCommandPath
$VenvDir    = Join-Path $Root '.venv'
$VenvPy     = Join-Path $VenvDir 'Scripts\python.exe'
$VenvPyW    = Join-Path $VenvDir 'Scripts\pythonw.exe'
$EntryFile  = Join-Path $Root 'run.py'
$StartupLnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'VoiceType.lnk'
$MenuDir    = Join-Path ([Environment]::GetFolderPath('Programs')) 'VoiceType'
$MenuLnk    = Join-Path $MenuDir 'VoiceType.lnk'
$KeyDir     = Join-Path $env:APPDATA 'VoiceType'
$KeyFile    = Join-Path $KeyDir 'openai.key'

function Write-Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# --------------------------------------------------------------------------
# Stopping
# --------------------------------------------------------------------------

function Stop-VoiceType {
    <#
        Kills the app and any transcription worker it left behind.

        Workers matter. RealtimeSTT transcribes in a spawned child process,
        and a version of VoiceType from before the job object in
        voicetype/winjob.py could orphan one. An orphan spins on a broken
        pipe, logging a traceback per iteration, and will happily write
        gigabytes. Installs from now on cannot create them, but an upgrade
        should still clear out any that are already running.
    #>
    $all = @(Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue)
    if (-not $all) { return }

    $live = @{}
    foreach ($p in (Get-Process -ErrorAction SilentlyContinue)) { $live[$p.Id] = $true }

    $targets = New-Object System.Collections.Generic.List[object]

    $mains = @($all | Where-Object { $_.CommandLine -and $_.CommandLine -like '*run.py*' })
    foreach ($m in $mains) { $targets.Add($m) }
    $mainIds = @($mains | ForEach-Object { $_.ProcessId })

    foreach ($p in $all) {
        if (-not $p.CommandLine -or $p.CommandLine -notlike '*spawn_main*') { continue }
        $isOurs = $mainIds -contains $p.ParentProcessId
        # An orphan is one whose parent PID is gone entirely.
        $isOrphan = -not $live.ContainsKey($p.ParentProcessId)
        if ($isOurs -or ($isOrphan -and $p.CommandLine -like '*voicetype*')) {
            $targets.Add($p)
        }
    }

    foreach ($t in ($targets | Sort-Object ProcessId -Unique)) {
        Write-Host "  stopping PID $($t.ProcessId)"
        try { Stop-Process -Id $t.ProcessId -Force -ErrorAction Stop } catch {}
    }
    if ($targets.Count -gt 0) { Start-Sleep -Milliseconds 800 }
}

# --------------------------------------------------------------------------
# Uninstall
# --------------------------------------------------------------------------

if ($Uninstall) {
    Write-Step 'Stopping VoiceType'
    Stop-VoiceType
    Write-Step 'Removing shortcuts'
    foreach ($lnk in @($StartupLnk, $MenuLnk)) {
        if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Host "  removed $lnk" }
    }
    if ((Test-Path $MenuDir) -and -not (Get-ChildItem $MenuDir)) {
        Remove-Item $MenuDir -Force
    }
    Write-Host "`nVoiceType will no longer start automatically." -ForegroundColor Green
    Write-Host "Still on disk, delete by hand if you want them gone:"
    Write-Host "  the project folder   $Root"
    Write-Host "  its environment      $VenvDir"
    if (Test-Path $KeyFile) { Write-Host "  your API key         $KeyFile" }
    return
}

# --------------------------------------------------------------------------
# API key
# --------------------------------------------------------------------------

function Set-ApiKey {
    Write-Step 'OpenAI API key'
    Write-Host 'Paste your key (it will not be echoed), or press Enter to skip.'
    Write-Host 'Get one at https://platform.openai.com/api-keys'
    $secure = Read-Host -AsSecureString '  Key'
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if ([string]::IsNullOrWhiteSpace($plain)) {
        Write-Host '  skipped; VoiceType will keep transcribing locally.'
        return
    }
    $plain = $plain.Trim()
    if ($plain -notmatch '^sk-') {
        Write-Warning '  That does not look like an OpenAI key. Saving it anyway.'
    }

    if (-not (Test-Path $KeyDir)) { New-Item -ItemType Directory -Path $KeyDir -Force | Out-Null }
    # Written without a BOM. The app reads it as utf-8-sig either way, but
    # other tools are less forgiving.
    [IO.File]::WriteAllText($KeyFile, $plain, (New-Object Text.UTF8Encoding($false)))
    # Break inheritance so only this account can read it.
    & icacls $KeyFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Write-Host "  saved to $KeyFile" -ForegroundColor Green
    Write-Host "  readable only by $($env:USERNAME), and outside the project"
    Write-Host "  folder on purpose so it can never be committed."
}

if ($SetApiKey) {
    Set-ApiKey
    Write-Host "`nRestart VoiceType for it to pick the key up:" -ForegroundColor Cyan
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\install.ps1"
    return
}

# --------------------------------------------------------------------------
# Find a Python
# --------------------------------------------------------------------------

function Test-PythonVersion([string]$exe) {
    # RealtimeSTT declares python_requires >=3.11,<3.13.
    try {
        $out = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    } catch { return $false }
    if ($LASTEXITCODE -ne 0 -or -not $out) { return $false }
    return ($out.Trim() -in @('3.11', '3.12'))
}

function Find-Python {
    if ($Python) {
        if (-not (Test-Path $Python)) { throw "No python.exe at $Python" }
        if (-not (Test-PythonVersion $Python)) {
            throw "$Python is not Python 3.11 or 3.12."
        }
        return $Python
    }

    # The py launcher is the reliable way to ask for a specific version.
    foreach ($v in @('3.12', '3.11')) {
        try {
            $found = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $found) { return $found.Trim() }
        } catch {}
    }

    foreach ($name in @('python.exe', 'python3.12.exe', 'python3.11.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and (Test-PythonVersion $cmd.Source)) { return $cmd.Source }
    }

    throw @"
Could not find Python 3.11 or 3.12.

VoiceType needs one of those two versions, because RealtimeSTT declares
python_requires >=3.11,<3.13. Python 3.13 will not work.

  1. Install it from https://www.python.org/downloads/
     (tick "Add python.exe to PATH" in the installer)
  2. Run this script again.

Already have one somewhere unusual? Point at it directly:
  .\install.ps1 -Python "C:\Path\To\python.exe"
"@
}

# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------

if (-not (Test-Path $EntryFile)) {
    throw "run.py not found. Run this script from inside the VoiceType folder."
}

Write-Step 'Stopping any running copy'
Stop-VoiceType

if (Test-Path $VenvPyW) {
    Write-Step "Using the existing environment at $VenvDir"
} else {
    $py = Find-Python
    Write-Step "Creating the environment with $py"
    & $py -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}

Write-Step 'Installing dependencies (the first run downloads a few hundred MB)'
& $VenvPy -m pip install --upgrade pip --quiet
& $VenvPy -m pip install -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed. Scroll up for the reason.' }

# --------------------------------------------------------------------------
# Shortcuts
# --------------------------------------------------------------------------

$shell = New-Object -ComObject WScript.Shell

function New-VoiceTypeShortcut([string]$Path) {
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
    $sc = $shell.CreateShortcut($Path)
    # pythonw.exe, not python.exe: this is what keeps a console off the screen.
    $sc.TargetPath       = $VenvPyW
    $sc.Arguments        = '"{0}"' -f $EntryFile
    $sc.WorkingDirectory = $Root
    $sc.WindowStyle      = 7
    $sc.Description      = 'VoiceType - hold Ctrl+Alt to dictate'
    $sc.IconLocation     = "$VenvPyW,0"
    $sc.Save()
    Write-Host "  created $Path"
}

Write-Step 'Creating shortcuts'
if ($NoAutostart) {
    if (Test-Path $StartupLnk) { Remove-Item $StartupLnk -Force }
    Write-Host '  skipping autostart (-NoAutostart)'
} else {
    New-VoiceTypeShortcut $StartupLnk
}
New-VoiceTypeShortcut $MenuLnk

# --------------------------------------------------------------------------
# Launch
# --------------------------------------------------------------------------

if (-not $NoStart) {
    Write-Step 'Starting VoiceType'
    Start-Process -FilePath $VenvPyW -ArgumentList "`"$EntryFile`"" -WorkingDirectory $Root
    Start-Sleep -Seconds 3
    $running = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*run.py*' }
    if ($running) {
        Write-Host "  running (PID $($running.ProcessId))" -ForegroundColor Green
    } else {
        Write-Warning "  it is not running. Check logs\voicetype.log."
    }
}

if (Test-Path $KeyFile) { $keyState = 'set' } else { $keyState = 'not set (transcribing locally)' }
if ($NoAutostart) { $autoState = 'off' } else { $autoState = 'on, via the Startup folder' }

Write-Host @"

--------------------------------------------------------------------
 VoiceType is installed.
--------------------------------------------------------------------

  Hold  Ctrl+Alt      record while held; release and the text is typed
  Tap   Ctrl+Alt      hands-free: keeps recording until you stop talking
                      or tap Ctrl+Alt again
  Any other key       cancels the recording

  Every transcript is also copied to the clipboard.

  Folder    : $Root
  OpenAI key: $keyState
  Autostart : $autoState

The first dictation after a reboot takes a few seconds longer while the
speech model loads. The tray icon shows status, switches language, and quits.

  Add a key       .\install.ps1 -SetApiKey
  Check your mic  .venv\Scripts\python.exe tools\check_mic.py
  Remove          .\install.ps1 -Uninstall
"@ -ForegroundColor Cyan
