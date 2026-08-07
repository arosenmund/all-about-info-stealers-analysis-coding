# test-windows-script

A drop-in kit that seeds a **Windows lab machine** with a realistic collection
of synthetic credential artifacts, so students and tooling can practice
credential hunting, and so detections can be validated end-to-end.

- `artifacts/` — 22 credential files in their genuine on-disk **formats**
  (teaching comments stripped) with **fake, non-functional values**. Derived
  from `../windows-credential-samples/`.
- `MANIFEST.md` — the artifact → real-filesystem-location map (human readable).
- `Deploy-CredentialArtifacts.ps1` — writes each artifact to its real location.

## Run it (on a lab VM)

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\Deploy-CredentialArtifacts.ps1 -WhatIf     # dry run
.\Deploy-CredentialArtifacts.ps1             # deploy (run elevated for the C:\ paths)
.\Deploy-CredentialArtifacts.ps1 -Remove     # clean up
```

Per-user artifacts (`.aws`, `.ssh`, browser stores, Desktop, etc.) deploy
without elevation. Machine-wide artifacts (`C:\inetpub`, `C:\Windows\Panther`,
`C:\ProgramData\...`, `C:\certs`) need an elevated PowerShell and are skipped
with a warning otherwise.

## Safety

Everything here is **fake** — RFC 5737 IPs, `example.com`, AWS's published
example keys, synthetic hashes and key blocks. None of it authenticates to
anything. Deploy it only on throwaway lab machines; it exists to *look like*
loot, not to be loot.
