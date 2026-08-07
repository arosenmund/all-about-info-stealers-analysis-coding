# test-windows-script — artifact → filesystem location map

22 synthetic credential artifacts and where they belong on a Windows host. The
files in `artifacts/` are the genuine on-disk *formats* (teaching comments
stripped) with **fake values** — realistic to hunt for, useless to authenticate
with. `Deploy-CredentialArtifacts.ps1` writes each to the destination below.

`%USERPROFILE%` = `C:\Users\<you>`. Rows marked **admin** write to machine-wide
paths and require an elevated PowerShell.

| # | artifacts/ file | Deploys to | Credential type | Admin |
|---|---|---|---|:--:|
| 1 | `aws-credentials` | `%USERPROFILE%\.aws\credentials` | AWS access key + secret | |
| 2 | `gcloud-application_default_credentials.json` | `%APPDATA%\gcloud\application_default_credentials.json` | GCP OAuth refresh token | |
| 3 | `gcp-service-account.json` | `%USERPROFILE%\Downloads\example-prod-0e5c.json` | GCP service-account private key | |
| 4 | `azure-sp.json` | `%USERPROFILE%\Downloads\sp-terraform-prod.json` | Azure service-principal secret | |
| 5 | `kube-config` | `%USERPROFILE%\.kube\config` | Kubernetes token + client key | |
| 6 | `docker-config.json` | `%USERPROFILE%\.docker\config.json` | Registry basic-auth (base64) | |
| 7 | `id_ed25519` | `%USERPROFILE%\.ssh\id_ed25519` | SSH private key | |
| 8 | `oci-config` | `%USERPROFILE%\.oci\config` | OCI API key ref + passphrase | |
| 9 | `oci_api_key.pem` | `%USERPROFILE%\.oci\oci_api_key.pem` | OCI API signing key | |
| 10 | `git-credentials` | `%USERPROFILE%\.git-credentials` | GitHub/GitLab/Bitbucket tokens | |
| 11 | `ConsoleHost_history.txt` | `%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt` | Inline creds in shell history | |
| 12 | `web.config` | `C:\inetpub\wwwroot\PayrollApp\web.config` | SQL conn string + machineKey | **✓** |
| 13 | `appsettings.Production.json` | `C:\inetpub\wwwroot\PayrollApp\appsettings.Production.json` | DB/Stripe/Azure secrets | **✓** |
| 14 | `app.env` | `%USERPROFILE%\source\repos\shop\.env` | Mixed API keys / DB URL | |
| 15 | `unattend.xml` | `C:\Windows\Panther\unattend.xml` | Base64 admin password | **✓** |
| 16 | `wlan-CorpWLAN.xml` | `C:\ProgramData\Microsoft\Wlansvc\Profiles\Interfaces\{DC2E9F1A-…}\{A7F3C1D2-…}.xml` | WiFi PSK | **✓** |
| 17 | `WinSCP.ini` | `%APPDATA%\WinSCP.ini` | Saved SFTP/FTP passwords | |
| 18 | `prod-fileserver.rdp` | `%USERPROFILE%\Documents\prod-fileserver.rdp` | Saved RDP credential (DPAPI blob) | |
| 19 | `passwords.txt` | `%USERPROFILE%\Desktop\passwords.txt` | The classic plaintext list | |
| 20 | `firefox-logins.json` | `%APPDATA%\Mozilla\Firefox\Profiles\7k2f9x1q.default-release\logins.json` | Firefox saved logins | |
| 21 | `server.key` | `C:\certs\server.key` | RSA private key | **✓** |
| 22 | `chrome-Local-State.json` | `%LOCALAPPDATA%\Google\Chrome\User Data\Local State` | Chrome DPAPI-wrapped master key | |

## Usage

```powershell
# From an elevated PowerShell (admin rows are skipped if not elevated):
Set-ExecutionPolicy -Scope Process Bypass -Force
.\Deploy-CredentialArtifacts.ps1                 # deploy everything possible
.\Deploy-CredentialArtifacts.ps1 -WhatIf         # preview, write nothing
.\Deploy-CredentialArtifacts.ps1 -Remove         # remove what it deployed
```

> Lab machines only. Everything here is fake; deploying it on a real endpoint
> just litters synthetic bait. See `../windows-credential-samples/README.md`.
