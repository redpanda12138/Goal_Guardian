# Chapters 1-2 Citation Augmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 12-18 verified, high-quality references to Chapters 1 and 2 and integrate them into specific claims without changing the dissertation's research questions, contributions, or prototype scope.

**Architecture:** Build a claim-evidence map from the existing chapter structure, select sources by evidence tier, then update the shared BibTeX database before integrating citations into each chapter. Verification proceeds from metadata checks to citation-key integrity and finally a full LaTeX build.

**Tech Stack:** LaTeX, BibTeX, IEEE-style citations, PowerShell, `rg`, DOI/publisher/proceedings metadata, and the existing NTU dissertation build toolchain.

---

### Task 1: Establish the citation baseline and claim-evidence map

**Files:**
- Read: `ntu-dissertation/latex/chapter-1/chapter-1.tex`
- Read: `ntu-dissertation/latex/chapter-2/chapter-2.tex`
- Read: `ntu-dissertation/latex/c-back-matter/references.bib`

- [ ] **Step 1: Extract all citation keys from Chapters 1 and 2**

Run:
```powershell
rg -o '\\cite\{[^}]+\}' ntu-dissertation/latex/chapter-1/chapter-1.tex ntu-dissertation/latex/chapter-2/chapter-2.tex
```

Expected: the current baseline shows 8 unique keys in Chapter 1 and 15 unique keys in Chapter 2.

- [ ] **Step 2: Map unsupported or thinly supported claims**

Record candidate claims under the existing sections: health coaching scope; goal review and feedback; digital-health engagement; conversational-agent evidence; LLM coaching limitations; longitudinal memory/state; multi-agent coordination; and responsible-AI boundaries.

- [ ] **Step 3: Confirm protected content**

Verify that the research aim, objectives, RQ1-RQ4, named contributions, and prototype-only effectiveness boundary are marked as substantively unchanged.

### Task 2: Discover and verify 12-18 candidate references

**Files:**
- Modify later: `ntu-dissertation/latex/c-back-matter/references.bib`

- [ ] **Step 1: Search by evidence cluster**

Use focused searches for: health coaching systematic review or meta-analysis; goal setting plus self-monitoring and feedback; mobile-health engagement and attrition; health conversational-agent safety and effectiveness; LLM healthcare safety or evaluation; long-term conversational memory; and multi-agent healthcare workflow governance.

- [ ] **Step 2: Apply the evidence hierarchy**

Prioritize systematic reviews, meta-analyses, consensus or authoritative guidance, seminal theory, and peer-reviewed empirical work. Use preprints only when no peer-reviewed equivalent exists and the source directly concerns the dissertation's recent technical topic.

- [ ] **Step 3: Verify every candidate**

For every source, confirm title, complete author list, year, venue, volume/issue/pages or article number, and DOI through a DOI resolver, publisher page, official proceedings page, PubMed, Crossref, or an official repository.

- [ ] **Step 4: Enforce the target size**

Retain 12-18 sources whose claims can be integrated directly. Reject duplicate evidence, tangential papers, inaccessible metadata, and sources whose findings would require overstating clinical effectiveness.

### Task 3: Add verified BibTeX records

**Files:**
- Modify: `ntu-dissertation/latex/c-back-matter/references.bib`

- [ ] **Step 1: Add one complete BibTeX entry per retained source**

Follow the existing field order and key style. Include `doi` whenever available; otherwise include a stable `url` or authoritative proceedings metadata.

- [ ] **Step 2: Check key uniqueness**

Run:
```powershell
rg '^@\w+\{([^,]+),' ntu-dissertation/latex/c-back-matter/references.bib
```

Expected: every newly added key appears exactly once.

- [ ] **Step 3: Inspect the BibTeX diff**

Run:
```powershell
git diff -- ntu-dissertation/latex/c-back-matter/references.bib
```

Expected: 12-18 new verified entries and no alteration of unrelated existing entries.

### Task 4: Strengthen Chapter 1

**Files:**
- Modify: `ntu-dissertation/latex/chapter-1/chapter-1.tex`

- [ ] **Step 1: Add 4-6 new-source citations to introductory claims**

Integrate sources into the Background, Problem Statement, Research Gap, and Scope and Limitations sections. Prefer sentence-level citation placement and make only small prose changes required for accurate attribution.

- [ ] **Step 2: Preserve thesis-specific claims**

Do not attach external citations to original descriptions of GoalGuardian unless the sentence also makes a literature-derived claim. Preserve the current RQs and contribution numbering.

- [ ] **Step 3: Inspect the chapter diff**

Run:
```powershell
git diff -- ntu-dissertation/latex/chapter-1/chapter-1.tex
```

Expected: evidence support is broader, but the chapter structure, study scope, and claimed contribution remain unchanged.

### Task 5: Strengthen Chapter 2

**Files:**
- Modify: `ntu-dissertation/latex/chapter-2/chapter-2.tex`

- [ ] **Step 1: Add 8-12 new-source citations across the literature streams**

Distribute evidence across health coaching and goal review; digital tailoring and engagement; conversational agents; LLM health coaching; agentic workflows; and responsible-AI considerations. Reuse Chapter 1 sources when they support the same evidence stream.

- [ ] **Step 2: Improve synthesis where evidence changes the balance**

Use brief sentence-level revisions to distinguish effectiveness, feasibility, acceptability, safety, and design implications. Keep Bloom and the MAS paper as design references rather than clinical-effectiveness evidence.

- [ ] **Step 3: Inspect the chapter diff**

Run:
```powershell
git diff -- ntu-dissertation/latex/chapter-2/chapter-2.tex
```

Expected: the review shows broader evidence coverage without turning into a list of studies or changing the identified research gap.

### Task 6: Audit citation integrity

**Files:**
- Verify: `ntu-dissertation/latex/chapter-1/chapter-1.tex`
- Verify: `ntu-dissertation/latex/chapter-2/chapter-2.tex`
- Verify: `ntu-dissertation/latex/c-back-matter/references.bib`

- [ ] **Step 1: Compare cited and defined keys**

Extract citation keys from both chapters and entry keys from the BibTeX file. Report undefined keys, duplicate BibTeX keys, and newly added entries not cited in either chapter.

- [ ] **Step 2: Check formatting and whitespace**

Run:
```powershell
git diff --check -- ntu-dissertation/latex/chapter-1/chapter-1.tex ntu-dissertation/latex/chapter-2/chapter-2.tex ntu-dissertation/latex/c-back-matter/references.bib
```

Expected: exit code 0 with no whitespace errors.

- [ ] **Step 3: Recount the augmentation**

Expected: 12-18 new BibTeX entries, at least 4 new sources used in Chapter 1, at least 8 new sources used in Chapter 2, and no unsupported increase in the dissertation's claims.

### Task 7: Compile and inspect the dissertation

**Files:**
- Build: `ntu-dissertation/latex/main.tex`

- [ ] **Step 1: Compile with the available LaTeX toolchain**

Run the bundled LaTeX compilation helper against the absolute path to `ntu-dissertation/latex/main.tex`; allow it to select the installed TeX Live/latexmk toolchain because the project uses BibTeX.

Expected: build exit code 0 and a generated PDF.

- [ ] **Step 2: Check the build log for citation failures**

Search the build output for `Citation`, `undefined`, `multiply defined`, `BibTeX`, and `error`.

Expected: no undefined citations, duplicate labels caused by this change, or BibTeX errors.

- [ ] **Step 3: Review the final diff against the approved design**

Confirm that only the two chapter files and the bibliography were modified for implementation, all sources were verified, and the RQs, contributions, and prototype scope remain intact.
