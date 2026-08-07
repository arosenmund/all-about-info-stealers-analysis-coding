## First Confirmed Theft Target — WinSCP Saved Sessions

### 1. Pick up the trail from our first triage pass

Back in the Quick Triage, we flagged the registry string `Software\Martin Prikryl\WinSCP 2\Sessions` (`140087418`) as a lead — WinSCP is an SFTP/FTP client, and it stores saved server credentials under that key. Let's confirm, with code, that this string is actually *used* rather than just sitting in `.rdata`.

1. In Defined Strings (or Listing), navigate to `140087418`.
2. Right-click → **References → Show References to Address**. You'll land inside `FUN_1400423a8`.

### 2. `FUN_1400423a8` — the harvester

Rename this one in your notes as **`harvest_winscp_sessions`**. Walking the decompiled code:

```c
RegOpenKeyExA(HKEY_CURRENT_USER, "Software\\Martin Prikryl\\WinSCP 2\\Sessions", 0, KEY_READ, &local_res10);
...
RegEnumKeyExA(local_res10, dwIndex, lpName, ...);   // enumerate each saved session's subkey
FUN_140007e88(local_218, local_148, lpName);         // store the session name
plVar5 = FUN_140041800(local_188, local_res10, local_148, "HostName");   // read HostName value
plVar5 = FUN_140041800(local_188, local_res10, local_148, "UserName");   // read UserName value
local_198 = FUN_1400418d8(local_res10, local_148, pCVar6);               // read PortNumber value
FUN_140041800(local_168, local_res10, local_148, "Password");            // read Password value (still obfuscated!)
if (local_158 != 0) {
    plVar5 = FUN_140041ad4(local_188, local_1d8, local_1f8, local_168);  // decode the password
    ...
}
```

3. `FUN_140041800` is a thin wrapper around `RegQueryValueExA` — confirmed by checking its body (it calls through `DAT_1400bcce8`, one of the dynamically-resolved ADVAPI32 pointers we mapped in the previous section).
4. The loop repeats `RegEnumKeyExA` until it returns `ERROR_NO_MORE_ITEMS` (`0x103`), so this walks **every** saved session under that registry key, not just one.
5. For each session it collects: session name, `HostName`, `UserName`, `PortNumber`, and — if present — the `Password` value.

### 3. The password isn't stored in cleartext by WinSCP — so there's a decoder

6. Open `FUN_140041ad4`. This is the interesting part: WinSCP obfuscates saved passwords with a simple, publicly-documented XOR scheme (not real encryption) keyed off part of the username/hostname. Notice the tell in the decompiled code:
   ```c
   local_res20 = ((int)lVar5 * 0x10 + (int)lVar6 ^ 0x5cU) & 0xff;
   ```
   That `^ 0x5c` and the hex-nibble reconstruction (`"0123456789ABCDEF"` lookup table) is the classic **WinSCP password "obfuscation" reversal** — this function is a from-scratch reimplementation of WinSCP's own (in)famous weak password storage, written into the stealer specifically to decode what it just read from the registry.
7. The decoded plaintext password flows back into `FUN_1400426c0` (the caller), which formats everything — session name, host, port, username, and now the **decoded** password — into a text report using string-stream helpers (`FUN_14001c734`, `FUN_14001d7bc`).

### 4. Where the stolen data goes

8. Look further down in `FUN_1400426c0`:
   ```c
   FUN_140007f9c(&local_190, "soft\\WinSCP\\winscp.txt", ...);
   FUN_14000ccc0(local_150, (undefined8 *)(param_1 + 0x20), &local_190, local_170);
   ```
   The formatted report — every harvested session, host, user, and decoded password — gets written out under the filename `winscp.txt` (relative to a base path passed in via `param_1 + 0x20`; we'll pin down exactly where that base path resolves to — likely the same staging directory as other stolen-data files — in a later section on the collection/upload flow).

### 5. Confirming reachability (why this matters more than the earlier string alone)

9. Check the call graph: **Window → Function Call Graph**, or use **Xrefs**: `FUN_1400423a8` ← `FUN_1400426c0` ← `FUN_14002bb44` ← `FUN_14002c1f4` ← `__scrt_common_main_seh` (the CRT-generated wrapper that calls the real `main`).
10. That's a **fully reachable path from program entry** — unlike the lone `stealc` PDB string (which only told us about the developer's build environment), this is: real code, calling real Windows registry APIs, decoding real WinSCP password obfuscation, and writing the result to a named file. This is what elevates "credential theft" from a hypothesis to a **confirmed static capability** — the binary contains a complete, reachable implementation of WinSCP credential harvesting.
11. One caveat worth keeping in your notes for the final report: reachable-from-main is strong evidence, but it's still static analysis. To call this a *confirmed runtime behavior* rather than a *confirmed capability*, you'd want to see it actually execute (e.g., in a sandbox with a WinSCP install present) — keep that distinction sharp when you write this up later.
