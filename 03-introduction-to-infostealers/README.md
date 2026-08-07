# 03 · Introduction to InfoStealers

**Lead:** Ryan · **Time:** 45 minutes

## Goal

Understand the InfoStealer ecosystem and use Ghidra to identify how a representative StealC sample discovers and selects target data.

## Topics

1. What an InfoStealer is and how the ecosystem has evolved.
2. Why StealC is a useful workshop case study.
3. What data modern stealers target and why.
4. A repeatable first-pass workflow in Ghidra.
5. Recognizing and removing analysis obstacles.
6. Tracing host enumeration and text-file targeting.
7. Identifying cryptocurrency-wallet collection logic.

## Analysis notebook

For each behavior, record:

| Question | Observation |
|---|---|
| What triggers the behavior? | |
| What APIs, paths, or data structures are involved? | |
| What data would a defender observe? | |
| Which assumption should we verify dynamically? | |

## References

- [Lumma Stealer analysis paper](../Resources-Ryan/Lumma_Stealer_Analysis.pdf)
- [StealC overview paper](../Resources-Ryan/StealC_stealer-Everything_you_need_to_know.pdf)

Only analyze the instructor-provided sample inside the workshop range.

---

[← Lab setup](../02-lab-environment-setup/) · [Workshop home](../) · **[Next: Advanced analysis →](../04-advanced-infostealer-analysis/)**
