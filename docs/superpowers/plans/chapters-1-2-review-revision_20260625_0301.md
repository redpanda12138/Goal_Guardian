# Chapters 1--2 Review Revision Implementation Plan

> **For agentic workers:** Use the approved reviewer comments as the revision contract. A sub-agent performs the independent post-edit review; the primary agent applies any resulting corrections.

**Goal:** Revise Chapters 1--2 and keep evaluation terminology consistent across Chapters 1, 3, and 5.

**Architecture:** Make bounded LaTeX edits without changing study claims or adding references. Chapter 1 defines the objectives and research questions; Chapter 2 strengthens synthesis and critical positioning; Chapters 3 and 5 use the same five evaluation dimensions. The comparison table moves to a landscape page and uses a defined Yes/Partial/No scale.

**Tech Stack:** LaTeX, BibTeX/IEEE references, PowerShell static checks.

---

### Task 1: Align the research framing

**Files:** `chapter-1.tex`, `chapter-3.tex`, and `chapter-5.tex`.

- [x] Expand Objective 1 to functional and non-functional requirements.
- [x] Reframe RQ4 around all five evaluation dimensions.
- [x] Add an RQ-to-chapter mapping paragraph.
- [x] Describe speech input as implemented at prototype level but not clinically validated.
- [x] Add system traceability to the Chapter 5 evaluation scope and procedure.

### Task 2: Strengthen the literature review

**Files:** `chapter-2.tex` and `main.tex`.

- [x] Replace the numeric topic count with an inclusive description.
- [x] Preserve the distinction between comparative synthesis and research gap.
- [x] Add critical analysis of MAS overhead and failure modes.
- [x] Clarify the distinct roles of Bloom, the MAS paper, and GoalGuardian.
- [x] Reformat the synthesis table in landscape orientation, add longitudinal continuity, and define Yes/Partial/No.
- [x] Remove duplicated table-type wording caused by the template's `\thetable` definition.

### Task 3: Verify and review

- [x] Search for stale objective, RQ4, four-area evaluation wording, and `Table~\ref`.
- [x] Check environment balance and citation-key preservation.
- [x] Compile if a LaTeX engine is available; otherwise report the missing toolchain.
- [x] Dispatch an independent sub-agent review against every supplied comment.
- [x] Apply valid findings and rerun verification.
