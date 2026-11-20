# Copy proven RF500 code to E-Nose Pi5 #2. Run INTERACTIVELY on Windows
# after the SSH account is available. Never stores/passes SSH passwords.
# The ORIGINAL RF500 model and metadata must be supplied from Pi5 #1;
# this script never retrains or creates a replacement model.
param(
    [string]$SshUser = "raspi5",
    [string]$HostIP = "100.94.161.96",
    [string]$ModelPath,
    [string]$MetadataPath,
    [switch]$StageCodeOnly,
    [switch]$EnableAutostart
)
$ErrorActionPreference = 'Stop'
if ($HostIP -ne "100.94.161.96") { throw "SECOND_PI_IP_NOT_PINNED" }
if ($SshUser -notmatch '^[a-z_][a-z0-9_-]{0,30}$') { throw "SSH_USER_INVALID" }
if ($StageCodeOnly -and $EnableAutostart) { throw "CANNOT_ENABLE_WITHOUT_MODEL" }
if (-not $StageCodeOnly) {
    if (-not $ModelPath -or -not $MetadataPath) { throw "ORIGINAL_RF500_MODEL_AND_METADATA_PATH_REQUIRED" }
    if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) { throw "MODEL_NOT_FOUND" }
    if (-not (Test-Path -LiteralPath $MetadataPath -PathType Leaf)) { throw "METADATA_NOT_FOUND" }
    if ((Split-Path -Leaf $ModelPath) -ne 'final_model.joblib' -or
        (Split-Path -Leaf $MetadataPath) -ne 'final_model_info.json') {
        throw "MODEL_FILENAMES_MUST_MATCH_TRUSTED_PI1_ARTIFACTS"
    }
    $expectedHash = 'B2B6E8D8FF03E92C695C1B0B55A8C06EA9D4178249C9CE012203E602FF1BCF5D'
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ModelPath).Hash.ToUpperInvariant()
    if ($actualHash -ne $expectedHash) { throw "MODEL_SHA256_MISMATCH_NEVER_LOAD_UNTRUSTED_JOBLIB" }
}

$remote = "${SshUser}@${HostIP}"
$opts = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10')
$pi2Identity = Join-Path $env:USERPROFILE '.ssh\id_ed25519_enose_pi2'
if (Test-Path -LiteralPath $pi2Identity -PathType Leaf) {
    $opts += @('-i', $pi2Identity)
}
$work = 'smart-coffee-stage7/rf30_staging/com5_integration/always_on'
$stage = 'smart-coffee-stage7/rf30_staging'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$scripts = (Resolve-Path (Join-Path $here '..')).Path

function Invoke-Checked([string]$Tool, [string[]]$Arguments) {
    & $Tool @Arguments
    if ($LASTEXITCODE -ne 0) { throw "${Tool}_FAILED_EXIT_${LASTEXITCODE}" }
}

Write-Host "Checking SSH to Pi5 #2 at $HostIP (may prompt interactively for an account password)..."
Invoke-Checked 'ssh' ($opts + @($remote, 'hostname; whoami; tailscale ip -4'))
Invoke-Checked 'ssh' ($opts + @($remote, "mkdir -p ~/$work ~/$stage && chmod 700 ~/$work"))

$sources = @(
    (Join-Path $scripts 'rf500_pi_persistent_listener.py'),
    (Join-Path $scripts 'pi_labeled_take_data.py'),
    (Join-Path $scripts 'rf30_pi_result_bridge.py'),
    (Join-Path $scripts 'roast_rf30_pi_inference.py'),
    (Join-Path $scripts 'roast_rf30_pi_stream_replay.py'),
    (Join-Path $scripts 'rf500_pi_verify_staged_bridge.py'),
    (Join-Path $here 'installer.py'),
    (Join-Path $here 'boot_supervisor.sh')
)
foreach ($src in $sources) {
    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "SOURCE_CODE_FILE_MISSING: $src" }
}
Invoke-Checked 'scp' ($opts + $sources + @("${remote}:$work/"))
Write-Host "Source scripts copied into the SECOND Pi staging, without touching Pi5 #1."

if ($StageCodeOnly) {
    Write-Host "CODE_ONLY_STAGED: No RF500 model present and no listener has been started."
    exit 0
}

Invoke-Checked 'scp' ($opts + @($ModelPath, $MetadataPath, "${remote}:$stage/"))

# Use the isolated environment from the former Pi pipeline, with pinned
# scikit-learn 1.7.2. Fail if Python venv, pip or network is unavailable.
$setup = "python3 -m venv ~/$stage/.venv && ~/$stage/.venv/bin/python -m pip install --disable-pip-version-check 'scikit-learn==1.7.2' 'joblib==1.6.0' 'pyserial==3.5'"
Invoke-Checked 'ssh' ($opts + @($remote, $setup))
Invoke-Checked 'ssh' ($opts + @($remote,
    "~/$stage/.venv/bin/python -B ~/$work/installer.py --check"))
if ($EnableAutostart) {
    Invoke-Checked 'ssh' ($opts + @($remote,
        "~/$stage/.venv/bin/python -B ~/$work/installer.py --install"))
    Invoke-Checked 'ssh' ($opts + @($remote,
        "~/$stage/.venv/bin/python -B ~/$work/installer.py --start"))
    Write-Host "Autostart and persistent listener requested; check READY in the log."
} else {
    Write-Host "CODE_AND_MODEL_STAGED_PREFLIGHT_PASS; listener not started. Use -EnableAutostart when ready."
}
