## Second Confirmed Theft Target — Foxmail Email Accounts

### 1. Pick up the trail from the feature flags

Recall the two *literal* JSON keys inside the config parser (`FUN_140027e2c`): `steal_winscp` (which we just traced) and `steal_foxmail`. We've done WinSCP — now let's follow Foxmail. Foxmail is a popular (especially in China) email client that stores account data, including saved mailbox credentials, on disk.

1. Two leads point us there. From the decoded-strings work, note `Software\Aerofox\FoxmailPreview` (`1400847f8`) and `Foxmail.exe` (`140084828`). Navigate to either and do **References → Show References to Address**.
2. Both land you inside `FUN_140009014`.

### 2. `FUN_140009014` — locate the Foxmail install / storage path

Rename it **`find_foxmail_storage`**. It does path discovery, not theft yet:

- `RegOpenKeyExA(HKCU, "Software\\Aerofox\\FoxmailPreview", ...)` then reads the `Executable` value (via `RegQueryValueExA` → `DAT_1400bcdb0`) to find where Foxmail is installed.
- It strips the trailing `Foxmail.exe` from that path and appends `\Storage\` — building the folder where Foxmail keeps per-account data.
- There's a fallback branch that handles the `Program Files` / `\VirtualStore\` redirection case (Windows file-system virtualization), so it also finds accounts for non-admin installs.
- Returns the resolved `...\Storage\` directory string.

### 3. `FUN_1400098e8` — the harvester (the caller)

3. Check the call graph on `FUN_140009014`: it's called by `FUN_1400098e8`. Open that.
4. This is the actual collection routine. Rename it **`harvest_foxmail_accounts`**. Its logic:
   - Calls `find_foxmail_storage` to get the `\Storage\` path; bails if empty.
   - `FUN_140009734` enumerates the subdirectories under `\Storage\` — i.e. one entry per configured mail account.
   - For each account folder, it builds a path to `\Accounts\Account.rec0` (string `140084868`) — the file Foxmail uses to store that account's settings and saved credentials.
   - It reads/parses each `Account.rec0` (`FUN_14001ff00`), then stages the result:
     ```c
     FUN_14000a34c(local_2e8, ..., "soft\\FoxMail\\", ..., <account name>, ...);  // build "soft\FoxMail\<account>"
     FUN_140009f7c(local_2c8, local_2e8, ".rec0");                                // append ".rec0"
     FUN_14000ade8(local_288, (param_1 + 0x20), local_2c8, local_res20, ...);     // add to the collection bundle
     ```
   - So each stolen account gets bundled under the name `soft\FoxMail\<account>.rec0` — mirroring the `soft\WinSCP\winscp.txt` naming convention we saw for WinSCP. Both feed the same collection object (`param_1 + 0x20`), which is the staging structure that later gets serialized and POSTed to C2.

### 4. Note on `FUN_14000ade8`

5. The bundling helper `FUN_14000ade8` is worth a quick peek but don't rabbit-hole: it takes the file content, and (as we saw in the earlier decode work) it's the same routine that chunks large data into `total_parts` / `part_index` JSON envelopes and Base64/RC4-processes them for exfil. In other words, Foxmail account files are collected and queued for upload through the shared exfil path — not written to a local report the way the human-readable WinSCP summary was.

### 5. Reachability

6. Call graph: `FUN_1400098e8` ← `FUN_14002bb44` ← `FUN_14002c1f4` ← `__scrt_common_main_seh`. Same dispatcher (`FUN_14002bb44`) that invokes the WinSCP harvester — this is the central "run all the stealer modules" function, and Foxmail is one more module hanging off it. **Reachable from entry, code-backed = confirmed capability.**

> **Same caveat as WinSCP:** this is a confirmed *capability* via static reachability. Confirming it *executes and produces output at runtime* (e.g. with Foxmail installed and accounts configured) is a dynamic-analysis step for the report, not something static analysis alone settles.

### 6. Worth noting for the bigger picture

7. `FUN_14002bb44` is shaping up to be the master module dispatcher — WinSCP and Foxmail both live under it. When you're ready, that function is the natural next pivot: enumerating everything it calls will give you the full list of theft modules (browsers, wallets, files grabber, etc.) in one place, rather than discovering them one string at a time.
