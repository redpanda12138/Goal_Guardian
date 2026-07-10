# Expand Dissertation References to 40 Design

## Goal

Increase the dissertation bibliography from 29 to exactly 40 unique, cited references by adding 11 verified sources.

## Scope

Modify only:

- `ntu-dissertation/latex/chapter-1/chapter-1.tex`
- `ntu-dissertation/latex/chapter-2/chapter-2.tex`
- `ntu-dissertation/latex/c-back-matter/references.bib`

Generate a new timestamped PDF in `ntu-dissertation/` after verification.

## Evidence Strategy

Select 11 non-duplicate sources verified through DOI or authoritative publisher metadata. Prioritize systematic reviews, peer-reviewed empirical studies, established design frameworks, and reporting or governance guidelines covering digital-health engagement, adaptive interventions, conversational-agent safety, medical LLMs, human-AI interaction, and early-stage AI evaluation.

## Integration

Every new source must support a specific claim in Chapter 1 or Chapter 2. No `\nocite` padding is allowed. Sentence-level revisions may improve claim-evidence alignment, but the research questions, contributions, system description, and prototype-focused scope remain unchanged.

## Quality Gates

- Exactly 40 unique BibTeX entries.
- Exactly 40 unique citation keys used across the dissertation.
- No duplicate keys, undefined citations, or orphan references.
- All 11 new entries include verified DOI metadata.
- Full LaTeX compilation exits successfully.
- The final timestamped PDF contains bibliography item `[40]`.
