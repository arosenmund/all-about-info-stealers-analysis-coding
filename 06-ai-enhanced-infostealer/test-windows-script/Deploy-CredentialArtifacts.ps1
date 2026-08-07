#Requires -Version 5.1
<#
.SYNOPSIS
    Seed a Windows lab machine with SYNTHETIC credential artifacts for
    credential-hunting / detection-engineering practice.

.DESCRIPTION
    Copies the fake credential files under .\artifacts\ to the real filesystem
    locations where such secrets normally live (see MANIFEST.md for the full
    map). Every value in every file is FAKE and non-functional - this litters a
    lab box with realistic bait, it does not expose anything.

    Machine-wide destinations (C:\inetpub, C:\Windows\Panther, C:\ProgramData,
    C:\certs) require an elevated session. When the script is not running as
    Administrator those rows are skipped with a warning; the per-user rows still
    deploy.

.PARAMETER Remove
    Delete the artifacts this script deploys instead of writing them (lab reset).

.EXAMPLE
    .\Deploy-CredentialArtifacts.ps1 -WhatIf
    Preview every action without writing anything.

.EXAMPLE
    .\Deploy-CredentialArtifacts.ps1
    Deploy everything the current privilege level allows.

.EXAMPLE
    .\Deploy-CredentialArtifacts.ps1 -Remove
    Remove the deployed artifacts.

.NOTES
    LAB USE ONLY. Synthetic data. Companion: MANIFEST.md,
    ..\windows-credential-samples\README.md
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [switch]$Remove
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ArtifactsDir = Join-Path $PSScriptRoot 'artifacts'

function Test-Administrator {
    $identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

$IsAdmin = Test-Administrator

# artifacts\<Source>  ->  <Dest> on the live filesystem.
# Env vars expand at runtime on the target host. NeedsAdmin marks machine-wide
# paths that require an elevated PowerShell.
$Map = @(
    [pscustomobject]@{ Source = 'aws-credentials';                              NeedsAdmin = $false; Dest = "$env:USERPROFILE\.aws\credentials" }
    [pscustomobject]@{ Source = 'gcloud-application_default_credentials.json';  NeedsAdmin = $false; Dest = "$env:APPDATA\gcloud\application_default_credentials.json" }
    [pscustomobject]@{ Source = 'gcp-service-account.json';                     NeedsAdmin = $false; Dest = "$env:USERPROFILE\Downloads\example-prod-0e5c.json" }
    [pscustomobject]@{ Source = 'azure-sp.json';                                NeedsAdmin = $false; Dest = "$env:USERPROFILE\Downloads\sp-terraform-prod.json" }
    [pscustomobject]@{ Source = 'kube-config';                                  NeedsAdmin = $false; Dest = "$env:USERPROFILE\.kube\config" }
    [pscustomobject]@{ Source = 'docker-config.json';                           NeedsAdmin = $false; Dest = "$env:USERPROFILE\.docker\config.json" }
    [pscustomobject]@{ Source = 'id_ed25519';                                   NeedsAdmin = $false; Dest = "$env:USERPROFILE\.ssh\id_ed25519" }
    [pscustomobject]@{ Source = 'oci-config';                                   NeedsAdmin = $false; Dest = "$env:USERPROFILE\.oci\config" }
    [pscustomobject]@{ Source = 'oci_api_key.pem';                              NeedsAdmin = $false; Dest = "$env:USERPROFILE\.oci\oci_api_key.pem" }
    [pscustomobject]@{ Source = 'git-credentials';                              NeedsAdmin = $false; Dest = "$env:USERPROFILE\.git-credentials" }
    [pscustomobject]@{ Source = 'ConsoleHost_history.txt';                      NeedsAdmin = $false; Dest = "$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt" }
    [pscustomobject]@{ Source = 'web.config';                                   NeedsAdmin = $true;  Dest = "C:\inetpub\wwwroot\PayrollApp\web.config" }
    [pscustomobject]@{ Source = 'appsettings.Production.json';                  NeedsAdmin = $true;  Dest = "C:\inetpub\wwwroot\PayrollApp\appsettings.Production.json" }
    [pscustomobject]@{ Source = 'app.env';                                      NeedsAdmin = $false; Dest = "$env:USERPROFILE\source\repos\shop\.env" }
    [pscustomobject]@{ Source = 'unattend.xml';                                 NeedsAdmin = $true;  Dest = "$env:SystemRoot\Panther\unattend.xml" }
    [pscustomobject]@{ Source = 'wlan-CorpWLAN.xml';                            NeedsAdmin = $true;  Dest = "$env:ProgramData\Microsoft\Wlansvc\Profiles\Interfaces\{DC2E9F1A-4B6C-4F8E-9A2D-1C3B5D7E9F0A}\{A7F3C1D2-8E4B-4C6A-9D0E-2F4A6B8C0D1E}.xml" }
    [pscustomobject]@{ Source = 'WinSCP.ini';                                   NeedsAdmin = $false; Dest = "$env:APPDATA\WinSCP.ini" }
    [pscustomobject]@{ Source = 'prod-fileserver.rdp';                          NeedsAdmin = $false; Dest = "$env:USERPROFILE\Documents\prod-fileserver.rdp" }
    [pscustomobject]@{ Source = 'passwords.txt';                                NeedsAdmin = $false; Dest = "$env:USERPROFILE\Desktop\passwords.txt" }
    [pscustomobject]@{ Source = 'firefox-logins.json';                          NeedsAdmin = $false; Dest = "$env:APPDATA\Mozilla\Firefox\Profiles\7k2f9x1q.default-release\logins.json" }
    [pscustomobject]@{ Source = 'server.key';                                   NeedsAdmin = $true;  Dest = "C:\certs\server.key" }
    [pscustomobject]@{ Source = 'chrome-Local-State.json';                      NeedsAdmin = $false; Dest = "$env:LOCALAPPDATA\Google\Chrome\User Data\Local State" }
)

Write-Host ""
Write-Host "==== SYNTHETIC credential-artifact deployer (LAB USE ONLY) ====" -ForegroundColor Cyan
Write-Host ("Artifacts source : {0}" -f $ArtifactsDir)
Write-Host ("Elevated         : {0}" -f $IsAdmin)
Write-Host ("Mode             : {0}" -f $(if ($Remove) { 'REMOVE' } else { 'DEPLOY' }))
Write-Host ""
if (-not $IsAdmin) {
    Write-Warning "Not elevated - machine-wide (admin) artifacts will be SKIPPED. Re-run as Administrator to deploy them."
}

$done = 0; $skipped = 0; $failed = 0

foreach ($item in $Map) {
    $src = Join-Path $ArtifactsDir $item.Source
    $dst = $item.Dest

    if ($item.NeedsAdmin -and -not $IsAdmin) {
        Write-Host ("  [skip] {0}  (needs admin)" -f $dst) -ForegroundColor DarkYellow
        $skipped++
        continue
    }

    try {
        if ($Remove) {
            if (Test-Path -LiteralPath $dst) {
                if ($PSCmdlet.ShouldProcess($dst, 'Remove artifact')) {
                    Remove-Item -LiteralPath $dst -Force
                    Write-Host ("  [del ] {0}" -f $dst) -ForegroundColor Green
                    $done++
                }
            }
            else {
                Write-Host ("  [none] {0}" -f $dst) -ForegroundColor DarkGray
                $skipped++
            }
            continue
        }

        if (-not (Test-Path -LiteralPath $src)) {
            Write-Warning ("source missing: {0}" -f $src)
            $failed++
            continue
        }

        $parent = Split-Path -Parent $dst
        if ($PSCmdlet.ShouldProcess($dst, 'Write artifact')) {
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $src -Destination $dst -Force
            Write-Host ("  [ok  ] {0}" -f $dst) -ForegroundColor Green
            $done++
        }
    }
    catch {
        Write-Warning ("failed: {0} -> {1}" -f $item.Source, $_.Exception.Message)
        $failed++
    }
}

$verb = if ($Remove) { 'removed' } else { 'deployed' }
Write-Host ""
Write-Host ("Done. {0} {1}, {2} skipped, {3} failed." -f $done, $verb, $skipped, $failed) -ForegroundColor Cyan
if (-not $Remove) {
    Write-Host "Reminder: every value is FAKE. Lab machines only." -ForegroundColor DarkGray
}
