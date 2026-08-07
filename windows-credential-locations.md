# Where Authentication Secrets Live on Windows

A hunt-oriented reference for the file (and registry) locations that hold
credentials, keys, and tokens on Windows hosts. Written for authorized security
testing, DFIR, and detection-engineering work — e.g. the "All About
Infostealers" material. Each category notes what protects the secret, because
file access alone is not always game over.

ATT&CK anchors: **T1552** (Unsecured Credentials), **T1555** (Credentials from
Password Stores), **T1003** (OS Credential Dumping).

---

## 1. OS credential stores (DPAPI-backed)

| Path | Contents |
|---|---|
| `%APPDATA%\Microsoft\Credentials\`, `%LOCALAPPDATA%\Microsoft\Credentials\` | Credential Manager blobs (saved RDP, network shares, generic creds) |
| `%LOCALAPPDATA%\Microsoft\Vault\`, `%PROGRAMDATA%\Microsoft\Vault\` | Web Credentials / Vault |
| `%APPDATA%\Microsoft\Protect\<SID>\` | DPAPI master keys — required to decrypt everything above |
| `%APPDATA%\Microsoft\Crypto\RSA\<SID>\`, `Crypto\Keys\` | Private key material for machine/user certs |

Protection: DPAPI. Needs the user's password (or their master key) or SYSTEM.
ATT&CK: **T1555.003/.004**, **T1552.001**.

## 2. Registry hives (files on disk)

- `%SystemRoot%\System32\config\{SAM,SECURITY,SYSTEM}` — local hashes, LSA
  secrets, cached domain creds, service-account passwords
- Frequently-readable backups: `C:\Windows\repair\`,
  `C:\Windows\System32\config\RegBack\`, and any VSS shadow copy
- `%SystemRoot%\NTDS\ntds.dit` on domain controllers (+ the SYSTEM hive for the
  boot key)

Protection: locked while online; grab via VSS/backup or SYSTEM.
ATT&CK: **T1003.002** (SAM), **T1003.004** (LSA), **T1003.005** (cached),
**T1003.003** (NTDS).

## 3. Memory and swap artifacts

`lsass.exe` dumps (`.dmp`), `C:\Windows\MEMORY.DMP`,
`%LOCALAPPDATA%\CrashDumps\`, WER dumps in
`C:\ProgramData\Microsoft\Windows\WER\`, plus `hiberfil.sys`, `pagefile.sys`,
`swapfile.sys`.

Protection: admin/SYSTEM to create or read.
ATT&CK: **T1003.001** (LSASS memory).

## 4. Deployment and GPO artifacts

- SYSVOL Group Policy Preferences XML: `Groups.xml`, `Services.xml`,
  `ScheduledTasks.xml`, `DataSources.xml`, `Drives.xml`, `Printers.xml`
  (`cpassword` — MS14-025; the AES key is public, so these are trivially
  decryptable)
- `unattend.xml` / `autounattend.xml` / `sysprep.inf` in `C:\Windows\Panther\`,
  `Panther\Unattend\`, `System32\Sysprep\`
- Autologon: `DefaultPassword` under `HKLM\...\Winlogon`
- WiFi PSKs: `C:\ProgramData\Microsoft\Wlansvc\Profiles\Interfaces\*\*.xml`
  (`keyMaterial`, DPAPI-machine)

Protection: mostly none once readable (GPP is the classic easy win); WiFi keys
need DPAPI-machine/SYSTEM.
ATT&CK: **T1552.006** (GPP), **T1552.001** (files).

## 5. Application config

`web.config`, `app.config`, `appsettings*.json`, `machine.config`, IIS
`applicationHost.config` (app-pool passwords, reversibly encrypted), `.env`,
`wp-config.php`, `settings.py`, `database.yml`, Jenkins `credentials.xml` +
`master.key` + `hudson.util.Secret`, McAfee `SiteList.xml`, Tomcat
`tomcat-users.xml`.

Protection: usually plaintext or reversible.
ATT&CK: **T1552.001**.

## 6. Developer / cloud tooling

In `%USERPROFILE%` unless noted:
`.aws\credentials`, `.azure\` (`msal_token_cache.bin`, `azureProfile.json`),
`%APPDATA%\gcloud\credentials.db` and `application_default_credentials.json`,
`.kube\config`, `.docker\config.json`, `.ssh\id_*`, `.git-credentials`,
`.npmrc`, `.pypirc`, `_netrc`, `%APPDATA%\NuGet\NuGet.Config`,
`terraform.tfstate` / `*.tfvars`, Ansible inventories and vault files.

Protection: mostly plaintext or base64; SSH keys may be passphrase-protected.
ATT&CK: **T1552.001**, **T1552.004** (private keys).

## 7. Remote-access clients

`.rdp` files, RDCMan `.rdg` / `RDCMan.settings`, PuTTY `.ppk`
(+ `HKCU\Software\SimonTatham\PuTTY\Sessions`), `WinSCP.ini`,
`%APPDATA%\FileZilla\sitemanager.xml` and `recentservers.xml` (base64, not
encryption), VNC password blobs in registry / `.ini`.

Protection: mixed — FileZilla is base64 (trivial); RDCMan/`.rdp` saved passwords
are DPAPI; VNC uses a fixed-key obfuscation (trivial).
ATT&CK: **T1552.001**, **T1555**.

## 8. Browsers and chat clients

- Chrome/Edge: `...\User Data\Default\Login Data`, `Cookies`, `Web Data`, plus
  `Local State` holding the DPAPI-wrapped key (newer builds add app-bound
  encryption)
- Firefox: `logins.json` + `key4.db` in the profile dir
- Slack/Teams/Discord/Electron apps: `Local Storage\leveldb\` and `Cookies` —
  bearer tokens in near-cleartext

Protection: DPAPI (Chromium) / NSS (Firefox); app-bound encryption raises the
bar on newer Chrome. This is the infostealer bread-and-butter.
ATT&CK: **T1555.003** (browsers), **T1539** (steal web session cookie).

## 9. History, scripts, and human habits

`ConsoleHost_history.txt` (PSReadLine), PowerShell transcripts,
`.ps1/.bat/.cmd/.vbs` with inline creds, scheduled-task XML in
`C:\Windows\System32\Tasks\`, Sticky Notes `plum.sqlite`, and the perennial
`passwords.txt` / `.xlsx` / OneNote `.one`.

Protection: none.
ATT&CK: **T1552.003** (bash/shell history equivalent), **T1552.001**.

## 10. Key and cert containers

`.pfx`, `.p12`, `.pem`, `.key`, `.jks`, `.keystore`, `.kdbx` (KeePass),
Bitwarden / 1Password local `data.json`.

Protection: usually passphrase- or master-password-protected.
ATT&CK: **T1552.004** (private keys), **T1555.005** (password managers).

## 11. Backups and images

`.vhd/.vhdx`, `.vmdk`, `.wim/.esd`, `.bak`, SQL `.mdf`, archives, and VSS
snapshots — these recreate every category above at a path with weaker ACLs.

Protection: inherits the source's protection but often at looser file
permissions.
ATT&CK: **T1552.001**, plus whatever the contained artifact maps to.

---

## Triage heuristic

Highest-yield hunts, roughly in order:

1. **DPAPI blobs + master keys together** (§1) — one without the other is dead
   weight.
2. **Config / IaC files** under source control or on shares (§5, §6) — often
   plaintext and widely readable.
3. **Anything in a backup or shadow copy** (§11) — same secrets, weaker ACLs.
4. **Command-line and history artifacts** (§9) — free, plaintext, and constantly
   regenerated.

Reality check: everything DPAPI-protected needs the user's password, their
master key, or SYSTEM-level access — so file access alone isn't always
game over for categories **1**, **4 (WiFi)**, and **8**.

---

## Related ATT&CK techniques (quick index)

| ID | Technique | Sections |
|---|---|---|
| T1003.001 | LSASS Memory | 3 |
| T1003.002 | Security Account Manager | 2 |
| T1003.003 | NTDS | 2 |
| T1003.004 | LSA Secrets | 2 |
| T1003.005 | Cached Domain Credentials | 2 |
| T1552.001 | Credentials In Files | 1, 4, 5, 6, 7, 9, 10, 11 |
| T1552.004 | Private Keys | 6, 10 |
| T1552.006 | Group Policy Preferences | 4 |
| T1555.003 | Credentials from Web Browsers | 8 |
| T1555.004 | Windows Credential Manager | 1 |
| T1555.005 | Password Managers | 10 |
| T1539 | Steal Web Session Cookie | 8 |
