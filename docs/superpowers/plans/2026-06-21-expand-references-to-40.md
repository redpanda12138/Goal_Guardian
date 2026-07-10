# Expand References to 40 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exactly 11 verified and cited references so the dissertation bibliography contains exactly 40 unique entries.

**Architecture:** Verify candidate DOI metadata, map each source to a specific claim in Chapters 1?2, then update BibTeX and prose together. Finish with key-integrity checks, a full Tectonic build, and a timestamped PDF.

**Tech Stack:** Crossref DOI metadata, LaTeX, BibTeX, IEEEtran, PowerShell, Tectonic, PyPDF2.

---

### Task 1: Verify and screen 11 candidate sources

Verify these DOI candidates against Crossref and reject any duplicate or metadata mismatch:

- `10.1016/j.pec.2014.07.026`
- `10.1002/ejsp.674`
- `10.2196/jmir.4055`
- `10.2196/jmir.4790`
- `10.1007/s12160-016-9830-8`
- `10.2196/12887`
- `10.1001/jamainternmed.2016.0400`
- `10.1038/s41586-023-05881-4`
- `10.1038/s41591-020-1034-x`
- `10.1038/s41591-020-1037-7`
- `10.1145/3290605.3300233`

Expected: 11 valid, non-duplicate sources with complete title, author, venue, year, and DOI metadata.

### Task 2: Add BibTeX entries and integrate claims

**Files:**
- Modify: `ntu-dissertation/latex/c-back-matter/references.bib`
- Modify: `ntu-dissertation/latex/chapter-1/chapter-1.tex`
- Modify: `ntu-dissertation/latex/chapter-2/chapter-2.tex`

Add all 11 BibTeX entries with DOI fields. Cite every new key in a claim it directly supports; do not use `\nocite`. Preserve RQs, contributions, and prototype scope.

Expected: exactly 40 BibTeX keys and 40 cited unique keys.

### Task 3: Audit bibliography integrity

Check duplicate keys, undefined citations, orphan references, new DOI completeness, and total union.

Expected: entries=40, cited=40, duplicates=0, undefined=0, orphans=0, new DOI fields=11.

### Task 4: Compile and generate timestamped PDF

Compile `ntu-dissertation/latex/main.tex` with bundled Tectonic in a temporary directory. Copy the valid PDF to `ntu-dissertation/GoalGuardian_Dissertation_YYYYMMDD_HHmm.pdf`, using `_02`, `_03`, etc. on collision.

Expected: compiler exit code 0, valid `%PDF` signature, and extracted bibliography contains `[40]` but not `[41]`.
