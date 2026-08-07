## Enumerating the Full Module Dispatcher — `FUN_14002bb44`

This is the stealer's orchestrator. Have students open it and walk it top-to-bottom. The structure is: **(1) init/setup → (2) beacon to C2 & get config → (3) run each theft module gated on a config flag → (4) upload results & signal done.**

### Phase 1 — Initialization
| Call | Purpose |
|---|---|
| `FUN_140002be0` | The Base64+RC4 string-decoder init we already reversed — populates all obfuscated globals |
| `FUN_140040580` | The dynamic API resolver (`LoadLibraryA`/`GetProcAddress` for wininet, crypt32, gdi32, etc.) |
| `FUN_14002be48` | Builds the victim "profile" object (`local_148`) that every module writes into |

### Phase 2 — Beacon & config
| Call | Purpose |
|---|---|
| `FUN_14002888c` | Sends the initial POST to C2 (`http://91.212.150.246/85e1d65ca2fa44acae49.php`) and gets the JSON task config back. If it returns 0 (no config / no network), the whole module block below is skipped |
| `FUN_1400292a4` | **System fingerprint / recon** — collects hostname, username, locale, screen resolution, HWID (from `SOFTWARE\Microsoft\Cryptography MachineGuid`), OS version via `RtlGetVersion`, CPU/RAM (`GlobalMemoryStatusEx`), installed software (uninstall registry keys) and running processes (`CreateToolhelp32Snapshot`) |

### Phase 3 — Theft modules (each gated on a config flag byte)

The config parser (`FUN_140027e2c`) set a struct of boolean flags; here they're checked one by one:

| Flag / loop | Module function | What it steals |
|---|---|---|
| `iVar1 == 1/2/3` loop over browser list | `FUN_140022dac` (types 1&2), `FUN_1400252f4` (type 3) | **Chromium/Gecko browser data.** `FUN_140022dac` handles Chromium: reads `Local State`, and — note the `VirtualAllocEx`/`WriteProcessMemory`/`QueueUserAPC` dynamic calls inside — performs **App-Bound-Encryption bypass** to decrypt cookies/passwords, staging them under `C:\ProgramData\...txt`. `FUN_1400252f4` handles the Gecko/`profiles.ini` path variant |
| `local_106` | `FUN_14002b5a0` | **Crypto wallets / browser-extension grabber** (walks the decoded wallet & extension key list — `Local Extension Settings`, `IndexedDB`, `chrome_extension_`, etc.) |
| `local_104` | `FUN_14001c31c` | **Microsoft Outlook** — enumerates Outlook profile registry keys (Office 13.0–16.0 + legacy Windows Messaging Subsystem), decrypts saved account creds, writes `soft\Outlook\outlook.txt` |
| `local_103` | `FUN_1400098e8` | **Foxmail** (the module we traced in section 06) |
| `local_102` | `FUN_1400426c0` | **WinSCP** (the module we traced in section 05) |
| `local_d0..local_c8` loop | `FUN_140008c98` → `FUN_140008a8c` | **File grabber** — iterates a list of file-target specs from the config (path/mask/recursion depth) and collects matching victim files |
| `local_105` | `FUN_1400392a4` | **Steam** — reads `Software\Valve\Steam` → `SteamPath`, grabs `\config\` files (`ssfn*`, `config.vdf`, `loginusers.vdf`, `libraryfolders.vdf`, etc.) for session hijacking |
| `local_107` | inline (`FUN_140050140` + `FUN_14003eb20`) | **Screenshot** — captures the screen (via the decoded GDI APIs `GetDC`/`CreateCompatibleBitmap`/`BitBlt`/GdiPlus) and uploads it as `screenshot.jpg` |

### Phase 4 — Finalize
| Call | Purpose |
|---|---|
| `FUN_140028fec` | Serializes the collected profile and POSTs the bundled data to C2 (sends the `done`/`opcode` envelope) |
| `FUN_14002b5a0` (if `local_106` was 0) | Fallback ordering for the wallet/extension module |
| `FUN_14003fba8` (if `local_108`) | Optional **self-delete / cleanup** (uses the decoded `cmd.exe`/`powershell.exe`/`msiexec.exe` paths) |

### The full picture

So the confirmed capability set, all reachable from `main` via this one dispatcher:

- **Recon:** full host fingerprint (HWID, OS, hardware, installed software, process list)
- **Browsers:** Chromium (incl. App-Bound-Encryption bypass) + Gecko cookies/passwords/history/autofill
- **Crypto wallets & browser extensions**
- **Email clients:** Outlook + Foxmail
- **File-transfer creds:** WinSCP
- **Gaming:** Steam session files
- **File grabber:** config-driven arbitrary file theft
- **Screenshot capture**
- **Optional self-delete**

This is a textbook, full-featured **infostealer** — and this single function is the map of everything it does. The earlier per-string discoveries (WinSCP, Foxmail) were just two branches of this tree.

> **Same discipline as before:** every module above is a *statically-confirmed capability* (real code, resolved APIs, reachable from entry, gated by a live C2 config). Turning "capability" into "observed behavior" — and capturing the actual config the live C2 hands out — is the job of dynamic analysis / sandboxing, which is where you'd take this next.
