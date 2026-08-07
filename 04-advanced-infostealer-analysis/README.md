# 04 · Advanced InfoStealer Analysis

**Lead:** Ryan

**Time:** 75 minutes

## Goal

Analyze a StealC v2 sample in Ghidra in order to learn how it functions:
- What does it target?
- How does it access the data?
- How does it exfil the data?

Let's find out!

## Topics

- **[01-triage-stealc.md](01-triage-stealc.md)**: Initial triage of `sample.exe`: hashes, PE facts, compiler, YARA/attribution leads, static import surface, and the code-backed capability signals that shape the rest of the workshop.
    - So... how useful is AI when it comes to malware analysis? Quite helpful, but with caveats!
    - This triage was performed with OpenCode using Sonnet 5 in high effort mode. Simple, decent triage. Ryan will point out the wins and "meh's" of the output :).
- **[02-loading-sample.md](02-loading-sample.md)**: Getting started in Ghidra: launching the tool, creating the `stealc` project, importing the sample from disk, and running auto-analysis.
- **[03-strings-attribution.md](03-strings-attribution.md)**: Reviewing Defined Strings, flagging interesting artifacts, and filtering for `steal` to surface the `C:\builder_v2\stealc\json.h` PDB-style path (a lead, not proof).
- **[04-strings-decoding.md](04-strings-decoding.md)**: Following that path into the JSON config parser, finding the Base64+RC4 string decoder, recovering the RC4 key, and decoding the obfuscated strings: including the live C2 endpoint.
- **[05-winscp-credentials.md](05-winscp-credentials.md)**: First confirmed theft target: enumerating `WinSCP 2\Sessions`, reversing the WinSCP password de-obfuscation, and confirming reachability from `main`.
- **[06-foxmail-credentials.md](06-foxmail-credentials.md)**: Second confirmed theft target: locating the Foxmail `\Storage\` path, harvesting per-account `Account.rec0` files, and staging them for exfil.
- **[07-dispatcher-modules.md](07-dispatcher-modules.md)**: Mapping the master module dispatcher (`FUN_14002bb44`): init, C2 beacon/config, and every flag-gated theft module (browsers, wallets, Outlook, Steam, file grabber, screenshot, self-delete).
- **[08-exfiltration-http.md](08-exfiltration-http.md)**: The HTTP exfiltration path: the WinINet POST routine, the retry wrapper, and the chunked Base64+RC4 JSON upload protocol that ships data to the C2.
- **[09-browser-artifacts.md](09-browser-artifacts.md)**: Deep-dive on browser theft: profile discovery via app-data enumeration, extension/2FA artifact targeting, and database access (Restart-Manager raw copy + `Local State` master-key extraction).

## Investigation prompts

As you follow the code, separate facts from hypotheses:

- Which paths or profile names are hard-coded?
- What checks occur before a file is collected?
- Which strings, imports, and control-flow branches make useful pivots?
- Where could defenders interrupt or detect the sequence?
- How are installed browsers or extensions enumerated?

## Checkpoint

You should leave this section with an annotated call path for at least one browser-data behavior. We will use that behavioral model, not copied malware code, as the design input for the next section.

---

[← Intro analysis](../03-introduction-to-infostealers/) · [Workshop home](../) · **[Next: Writing a controlled proof of concept →](../05-writing-an-infostealer/)**
