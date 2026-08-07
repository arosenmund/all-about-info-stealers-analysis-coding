## Browser Artifacts Deep-Dive

Three helper functions carry this: `FUN_140022dac` (per-browser driver), `FUN_1400228c4` (per-profile enumerator), `FUN_140022680` (per-extension collector), and `FUN_14002001c` (the `Local State` / App-Bound-Encryption key extractor). All strings below were recovered with the Base64+RC4 routine from section 04.

---

### Q1. Browser profile discovery through application-data locations

Each browser is described by a struct (built in the config phase, deep-copied by `FUN_140021b98`) containing:
- an **application-data root path** (field at `+0x20`, e.g. an `%APPDATA%`/`%LOCALAPPDATA%`-relative Chromium user-data dir),
- three **feature-flag bytes** (`+0x40` cookies/passwords, `+0x41`, `+0x42` extensions) mirroring the config,
- vectors of profile-DB targets and extension targets.

Discovery is a two-level directory walk:

1. **Browser level** — `FUN_140022dac` takes the browser's user-data root and appends `\Local State` (`DAT_1400b9c00`). It confirms that file exists (`FUN_14003ef24`), then calls `FUN_14002001c` to pull the master key from it (Q3). The `param_3` byte selects one of two root-path variants via `FUN_14003ed98(…,0x1a)` vs `0x1c` — i.e. two different app-data base locations for the same browser family (e.g. the standard user-data dir vs. an alternate/rooted install).

2. **Profile level** — `FUN_1400228c4` globs the user-data root with `\*.*` and iterates it using the dynamically-resolved `FindFirstFileA`/`FindNextFileA` (`DAT_1400bcd98` / `DAT_1400bcd88`), closing with `FindClose` (`DAT_1400bcd68`). Each returned entry is filtered with `StrStrA` (`DAT_1400bcd60`) against `DAT_1400847c0` and `DAT_1400847c4` — the classic `"."` / `".."` skip. Every surviving subdirectory is treated as a **browser profile** (`Default`, `Profile 1`, `Profile 2`, …). This is how it finds *all* profiles without hardcoding their names.

So: **app-data root → enumerate immediate subdirectories → each is a profile.** No registry lookup for profiles; it's pure filesystem enumeration under the configured app-data path.

---

### Q2. Browser extension & 2FA artifact targeting

Inside the per-profile loop, `FUN_1400228c4` checks the three flag bytes and, for the extensions flag (`+0x42`), builds a target path and calls `FUN_140022680`. The extension-relevant decoded strings:

| Global | Decoded value |
|---|---|
| `DAT_1400b8520` | `Local Extension Settings` |
| `DAT_1400b9200` | `Sync Extension Settings` |
| `DAT_1400b8740` | `IndexedDB` |
| `DAT_1400b8ac0` | `chrome_extension_` |
| `DAT_1400b9740` | `_0_indexeddb_leveldb` |
| `DAT_1400b8480` | `CURRENT` |

The three `FUN_140022680` calls target, per profile:
1. `…\Local Extension Settings\<ext-id>` (flag `+0x40`)
2. `…\Sync Extension Settings\<ext-id>` (flag `+0x41`)
3. `…\IndexedDB\chrome_extension_<ext-id>_0_indexeddb_leveldb\` (flag `+0x42`) — assembled from `chrome_extension_` + the extension id + `_0_indexeddb_leveldb`.

`FUN_140022680` then verifies the LevelDB is live by checking for the `CURRENT` file (`DAT_1400b8480`) before collecting the directory. The `<ext-id>` values come from the config's extension list (the wallet/2FA extension IDs) — this is exactly the layout Chromium uses for extension-owned storage, so the stealer is scooping the **on-disk state of specific browser extensions**: crypto-wallet extensions and **2FA/authenticator extensions** (e.g. Authenticator-type add-ons), which live in these `Local Extension Settings` / `Sync Extension Settings` / `IndexedDB` LevelDB stores. Targeting is **extension-ID-driven from the C2 config**, not hardcoded here — consistent with the separate wallet/extension grabber `FUN_14002b5a0` we saw off the dispatcher.

---

### Q3. Browser database discovery & access patterns

Two distinct access patterns:

**a) `Local State` → master-key extraction (`FUN_14002001c`).**
- Opens the browser's `Local State` file with the resolved `CreateFileW` (`DAT_1400bcde8`), reads it via `GetFileSizeEx`/`ReadFile` (`DAT_1400bce90` / `DAT_1400bcea0`).
- Parses it as JSON and walks `os_crypt` (`DAT_1400b9de0`) → `encrypted_key`/`app_bound_encrypted_key` (`DAT_1400b8b20`).
- Base64-decodes the value (`CryptStringToBinaryA`, `DAT_1400bce78`), checks the 5-byte prefix `memcmp(…,"DPAPI",5)` (`140084600`), then decrypts. The `DPAPI` path uses `CryptUnprotectData` (`DAT_1400bce50`); note the presence of `VirtualAllocEx`/`WriteProcessMemory`/`QueueUserAPC` in the Chromium driver — the **App-Bound-Encryption (`APPB`) bypass** path that proxies the decrypt through a Chrome process. A recovered 32-byte AES key is written out as `v20.txt` (`DAT_1400b98c0`) / `v10.txt` (`DAT_1400b8fe0`) under a `keys\` (`DAT_1400b9880`) staging subtree.

**b) Profile databases → file collection.**
- Because the actual credential/cookie stores are SQLite/LevelDB files that Chromium keeps locked, the stealer doesn't query them with SQL. Instead `FUN_140022dac` uses the **Restart Manager** APIs (`RmStartSession`/`RmRegisterResources`/`RmGetList` — `DAT_1400bcbe0` etc., resolved from `rstrtmgr.dll`) to enumerate and force-release the processes holding a target DB, then raw-reads the file bytes. That's the `0x28600`-byte buffered read + `VirtualAlloc`/copy sequence in `FUN_140022dac`. This is the standard stealer trick to grab `Login Data`, `Cookies`, `Web Data`, `History` etc. even while the browser is running and holding a lock.
- Collected DBs/keys are handed to the chunked exfil path (`FUN_14000ccc0` → the section-08 uploader), or staged under `C:\ProgramData\…\<name>.txt`.

**Summary of the access model:** master key comes from JSON parsing of `Local State` + DPAPI/App-Bound decryption; the databases themselves are acquired by **Restart-Manager-assisted raw file copy** (not SQL queries), which both defeats file locks and avoids needing an SQLite engine in the binary.

---

### Discipline note

Everything above is statically confirmed (decoded strings, resolved APIs, reachable code). The *exact* set of profiles, extension IDs, and databases a given run touches is driven by the C2-delivered config — so the concrete target list is a dynamic-analysis question. Treat the extension-ID targeting as "capable of, and structured for" wallet/2FA theft; the live target list requires detonation to enumerate.
