# 06 · AI-Enhanced Collection

**Lead:** Aaron · **Time:** 45 minutes

## Goal

Explore how a small, local relevance model can rank synthetic artifacts, then compare that behavior with static, path-based selection.

## Topics

- The limitations of broad, hard-coded targeting.
- Features that can represent synthetic files without sending data elsewhere.
- Running a compact model in memory.
- Ranking artifacts by relevance and applying a confidence threshold.
- Comparing precision, explainability, performance, and defensive visibility.

## Lab flow

1. Establish a baseline using the static selector.
2. Review the provided model and synthetic training corpus.
3. Add instructor-directed feature extraction and scoring.
4. Compile and run the enhanced proof of concept.
5. Compare selected artifacts and false positives.
6. Discuss defensive detections for both approaches.

## Takeaway questions

- Did relevance scoring reduce unnecessary collection?
- Which features contributed most to the result?
- What new errors or blind spots did the model introduce?
- Which endpoint behaviors remain detectable regardless of selection method?
- How would a defender validate a suspected model-assisted collector?

## Wrap-up

You have followed the complete workshop arc: reverse engineer a behavior, describe it, implement a constrained analogue, test it, and evaluate a modern variation. Keep the analytical method—even when the malware family or technology changes.

---

[← Writing an InfoStealer](../05-writing-an-infostealer/) · **[Return to workshop home](../)**
