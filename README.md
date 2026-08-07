# All About Stoopie InfoStealers

### Malware analysis for understanding. Custom coding for true understanding.

Welcome to the hands-on DEF CON 34 workshop from **Ryan Chapman** ([@rj_chap](https://x.com/rj_chap)) and **Aaron Rosenmund** ([@arosenmund](https://x.com/arosenmund)).

> **Friday, August 7, 2026 · 2:00–6:00 PM · Las Vegas**
>
> Intermediate · Four hours · Bring a laptop with Wi-Fi and a modern browser

In the first half, Ryan guides you through reverse engineering a modern information stealer using Ghidra. In the second half, Aaron turns those observations into code, then explores how local machine-learning techniques can make collection more selective. Everything runs inside the isolated workshop lab.

## Start here

| # | Section | Lead | Time | What you will do |
|---:|---|---|---:|---|
| 01 | [Welcome & orientation](01-welcome-and-orientation/) | Ryan + Aaron | 10 min | Meet the instructors, understand the flow, and review the ground rules. |
| 02 | [Lab environment setup](02-lab-environment-setup/) | Aaron | 20 min | Connect to the OnDefend range and verify your workstation. |
| 03 | [Introduction to InfoStealers](03-introduction-to-infostealers/) | Ryan | 45 min | Learn the ecosystem and begin analyzing LummaC2 in Ghidra. |
| — | **Break** | | 15 min | |
| 04 | [Advanced InfoStealer analysis](04-advanced-infostealer-analysis/) | Ryan | 45 min | Trace browser, extension, and database collection behavior. |
| 05 | [Writing an InfoStealer](05-writing-an-infostealer/) | Aaron | 45 min | Build and test a controlled proof of concept based on the analysis. |
| — | **Break** | | 15 min | |
| 06 | [AI-enhanced collection](06-ai-enhanced-infostealer/) | Aaron | 45 min | Explore local relevance scoring and compare static and behavioral approaches. |

The scheduled modules total 240 minutes, including breaks. We may adjust the pace to fit the room.

## Before the workshop

- Bring a laptop with a working Wi-Fi adapter, a modern browser, and permission to join the conference network.
- No local VM is required; the online range does the heavy lifting.
- A general computing and networking background is helpful. Familiarity with debugging, reverse engineering, or compilation is useful but not required.
- Start with [Section 01](01-welcome-and-orientation/), then follow the **Next** link at the bottom of each section.

## Instructors

### Ryan Chapman · `@rj_chap`

Ryan is the author of SANS FOR528: Ransomware and Cyber Extortion, an instructor for FOR610: Reverse-Engineering Malware, and a threat hunter. He specializes in making complex malware behavior approachable through hands-on analysis.

[Website](https://incidentresponse.training/) · [LinkedIn](https://www.linkedin.com/in/ryanjchapman/) · [YouTube](https://www.youtube.com/ryanchapmanj)

### Aaron Rosenmund · `@ironcat`

Aaron is Managing Director of Tradecraft and Programs at OnDefend and serves as a red-team staff lead for Cyber Shield. His work spans threat emulation, defensive operations, cyber ranges, and practical security education.

[LinkedIn](https://www.linkedin.com/in/aaronrosenmund/) · [X](https://x.com/arosenmund)

## Safety and scope

This repository is for supervised security education in an isolated, authorized environment. Workshop exercises use controlled data and infrastructure. Do not run workshop code on production systems, against real user data, or anywhere you do not have explicit permission to test.

## Reference material

- [Ryan's workshop notes](dc34_workshop-all_about_stoopie_infostealers-rchapman.txt)
- [Submitted workshop outline](DefCon34_Workshop-Outline-2Amigos.txt)
- [Lumma Stealer analysis paper](Resources-Ryan/Lumma_Stealer_Analysis.pdf)
- [LummaC2 overview paper](Resources-Ryan/LummaC2_stealer-Everything_you_need_to_know.pdf)

---

Ready? **[Begin with welcome and orientation →](01-welcome-and-orientation/)**
