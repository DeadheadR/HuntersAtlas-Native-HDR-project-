param(
    [Parameter(Mandatory=$true)][ValidateSet('windows19','lantern')][string]$Target,
    [string]$Config,
    [switch]$PackageOnly
)
$ErrorActionPreference='Stop'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if(-not $Config){$Config=Join-Path $repoRoot '.local\build-inputs.json'}
if(-not (Test-Path -LiteralPath $Config)){
    throw 'Create .local\build-inputs.json using source\launchers\build-inputs.example.json and the build guide.'
}
$inputs=Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
$python=$env:ATLAS_BUILD_PYTHON
if(-not $python){$python=$inputs.python_exe}
if(-not $python -or -not (Test-Path -LiteralPath $python)){
    throw 'Set ATLAS_BUILD_PYTHON or python_exe in the local input file to a working Python 3.12+ executable.'
}
$buildArgs=@((Join-Path $PSScriptRoot 'build.py'),'--target',$Target,'--config',$Config)
if($PackageOnly){$buildArgs+='--package-only'}
& $python @buildArgs
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
