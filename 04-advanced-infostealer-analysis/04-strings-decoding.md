## Following the PDB Path — Decoding the C2 Strings

### 1. Pivot from the string

1. Recall the UTF-16 string we found earlier at `140084920`:
   ```
   C:\builder_v2\stealc\json.h
   ```
2. Right-click it → **References → Show References to Address**. You'll land inside a function whose body reads like a JSON key/value walker — this is `FUN_140027e2c` (Ghidra names it by its entry address since it hasn't been given a real name yet).
3. Open it in the decompiler (**Window → Decompile**, or double-click the function in the Listing / Function List).

### 2. Overview of `FUN_140027e2c`

Rename it in your notes as **`parse_c2_task_config`** — that's what it does. It takes a JSON object (matching the shape of an embedded `nlohmann::json` node — byte 0 is a type tag, `0x01` = object) and a handful of key lookups populate an output struct:

- It walks the JSON looking up a batch of keys, most of which are **not literal strings** in this function — they're pointers to global buffers (`DAT_1400b9560`, `DAT_1400ba060`, `DAT_1400b8d20`, etc.) that sit empty (all zero) in the raw binary.
- Two keys *are* literal, plaintext strings right there in the disassembly: `"steal_foxmail"` and `"steal_winscp"`. For each key found, it extracts a boolean and stores it into an output struct at increasing offsets — this looks like a feature-flag config: "should I steal Foxmail data? Should I steal WinSCP data?"
- Three more lookups, gated on the JSON value being an array (type tag `2`), hand off to three sub-parsers (`FUN_140034a34`, `FUN_140034e5c`, `FUN_14003512c`) — likely list-type config fields (e.g., target lists or grabber masks).

**The key observation:** most of the JSON keys this function looks up are *empty at rest* in the binary. Something fills them in before this function ever runs. That "something" is worth tracking down — it's the string decryption routine, and it's what actually explains the block of odd Base64-looking strings we noticed back in the Checking Strings section.

### 3. Finding the decoder

4. Right-click one of those empty globals (e.g. `DAT_1400b9560`) → **References → Show References to Address**. You'll find writes coming from a large function — `FUN_140002be0` — that runs early, called (transitively) from the real `main`.
5. Open `FUN_140002be0` in the decompiler. It's long, but the pattern repeats hundreds of times:
   ```c
   sVar1 = strlen("uX1Tua4Rbq684f9yFOL/sTOVVIwn");
   FUN_140007f9c(&local_68, "uX1Tua4Rbq684f9yFOL/sTOVVIwn", sVar1);
   puVar2 = FUN_140007cc0(local_48, &local_68);   // <-- the decoder
   ... store puVar2 into a global (e.g. DAT_1400b84c0) ...
   ```
   Every one of those odd Base64-looking strings from the earlier section gets passed through `FUN_140007cc0` and the result is stashed into a global. **This is the deobfuscation routine populating the config keys, DLL names, and (as we're about to see) the C2 URL.**

### 4. Reverse the algorithm

6. Follow `FUN_140007cc0` → it Base64-decodes its input (`FUN_140025fd4`), then calls `FUN_140025c04` with a second global (`&DAT_1400b8b60`) as a parameter.
7. `FUN_140025c04` is the capa-flagged **RC4 PRGA** function from our earlier triage. `DAT_1400b8b60` is empty at rest too — meaning the RC4 *key itself* is also one of the obfuscated strings, decoded once at startup and cached.
8. Find the very first blob decoded in `FUN_140002be0` — it stores into `DAT_1400b8b60` directly (no RC4 step, just Base64... actually check: is it decoded via `FUN_140007cc0` too, or raw?). In this sample, the plaintext RC4 key turns out to be:
   ```
   jpnJqZ4NXJwK2SR8Ol
   ```
   which itself is sitting **unencrypted** in `.rdata` at `140082a08` — the scheme only obfuscates the *payload* strings, not the key.

So the pipeline is: **Base64-decode → RC4 with key `jpnJqZ4NXJwK2SR8Ol` → plaintext**.

### 5. Decode it yourself

9. Pick any of the odd strings near `140082a08`, e.g. `uX1Tua4Rbq684f9yFOL/sTOVVIwn` (found at `140082b88`, referenced right inside `FUN_140002be0`). In a terminal (CyberChef works too, if you'd rather stay GUI-only):
   ```bash
   python3 -c "
   import base64
   def rc4(key, data):
       S=list(range(256)); j=0
       for i in range(256):
           j=(j+S[i]+key[i%len(key)])%256; S[i],S[j]=S[j],S[i]
       out=bytearray(); i=j=0
       for b in data:
           i=(i+1)%256; j=(j+S[i])%256; S[i],S[j]=S[j],S[i]
           out.append(b ^ S[(S[i]+S[j])%256])
       return bytes(out)
   key = b'jpnJqZ4NXJwK2SR8Ol'
   blob = base64.b64decode('uX1Tua4Rbq684f9yFOL/sTOVVIwn')
   print(rc4(key, blob))
   "
   ```
10. You should get:
    ```
    b'http://91.212.150.246'
    ```
11. Decode the very next blob in the same function, `/jESrKVad6Lurv8lR/j65WDaA4wo1MnB6A==` (address `140082ba8`):
    ```
    b'/85e1d65ca2fa44acae49.php'
    ```

**Put together, that's the C2 endpoint:** `http://91.212.150.246/85e1d65ca2fa44acae49.php`

### 6. What else decodes with this key

Running the same routine across the rest of the blobs in `FUN_140002be0` recovers a lot of context in one pass:

| Category | Decoded values |
|---|---|
| DLLs dynamically loaded | `kernel32.dll`, `advapi32.dll`, `gdiplus.dll`, `crypt32.dll`, `gdi32.dll`, `rstrtmgr.dll`, `ole32.dll`, `winhttp.dll`, `user32.dll`, `shlwapi.dll`, `shell32.dll`, `ntdll.dll` |
| Notable resolved APIs | `CryptUnprotectData`, `RegQueryValueExA/W`, `Process32FirstW/NextW`, `CreateToolhelp32Snapshot`, `WriteProcessMemory`, `VirtualAllocEx`, `CreateProcessA`, `BitBlt`/`GetDC` (screen capture) |
| Browser/credential artifacts | `Login Data`, `Cookies`, `Web Data`, `History`, `Local State`, `cookies.sqlite`, `places.sqlite`, `formhistory.sqlite`, `logins.json`, `profiles.ini` |
| Password-manager / crypto | `nss3.dll`, `NSS_Init`, `PK11_GetInternalKeySlot`, `PK11SDR_Decrypt`, `os_crypt`, `encrypted_key` |
| C2 protocol fields | `opcode`, `data`, `filename`, `upload_file`, `Content-Type: application/json\r\n`, `POST` |
| Output artifact names | `passwords.txt`, `v10.txt`, `v20.txt`, `wallets`, `browser: `, `profile: `, `url: `, `login: `, `password: ` |

12. **Note what this confirms vs. what it doesn't:** decoding these strings tells you the binary *contains* the capability to resolve these DLLs/APIs and *contains* a live-looking C2 URL and POST-request scaffolding — that's strong, code-adjacent evidence (much stronger than the lone `stealc` path string). It is still not runtime proof by itself; the next step (which we'll do later) is to confirm these decoded values are actually *reachable* from `main` and consumed by the HTTP POST function (`FUN_14000c508`) we noted in the triage — not just sitting decoded in memory unused.

**[Next: WinSCP Credentials →](./05-winscp-credentials.md)**