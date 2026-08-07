# 04 · Advanced InfoStealer Analysis

**Lead:** Ryan · **Time:** 45 minutes

## Goal

Continue the Ghidra investigation and trace how browser-related artifacts move from discovery to collection.

## Topics

- Browser profile discovery through application-data locations.
- Browser extension and two-factor-authentication artifact targeting.
- Browser database discovery and access patterns.
- Connecting static findings to potential host and network telemetry.

## Investigation prompts

As you follow the code, separate facts from hypotheses:

- Which paths or profile names are hard-coded?
- How are installed browsers or extensions enumerated?
- What checks occur before a file is collected?
- Which strings, imports, and control-flow branches make useful pivots?
- Where could defenders interrupt or detect the sequence?

## Checkpoint

You should leave this section with an annotated call path for at least one browser-data behavior. We will use that behavioral model—not copied malware code—as the design input for the next section.

---

[← Intro analysis](../03-introduction-to-infostealers/) · [Workshop home](../) · **[Next: Writing a controlled proof of concept →](../05-writing-an-infostealer/)**
