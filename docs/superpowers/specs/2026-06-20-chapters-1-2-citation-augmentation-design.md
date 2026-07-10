# Chapters 1-2 Citation Augmentation Design

## Objective

Strengthen the academic rigor and authority of Chapters 1 and 2 by adding approximately 12-18 verified, high-quality references. The revision will improve claim-evidence alignment without changing the research questions, claimed contributions, or prototype-focused scope.

## Scope

The work will modify only:

- `ntu-dissertation/latex/chapter-1/chapter-1.tex`
- `ntu-dissertation/latex/chapter-2/chapter-2.tex`
- `ntu-dissertation/latex/c-back-matter/references.bib`

Minor sentence-level revisions are permitted where needed to integrate evidence accurately. The chapter structure, research aim, objectives, research questions, system description, and contribution claims will remain substantively unchanged.

## Evidence Strategy

New references will be selected for direct relevance to specific claims. Priority will be given to:

1. Systematic reviews and meta-analyses on health coaching, goal setting, mobile health, conversational agents, and digital behavior change.
2. Seminal theoretical or methodological sources establishing concepts used by the dissertation.
3. Peer-reviewed empirical studies on LLM-based health coaching and behavior-change interfaces.
4. Authoritative guidance or consensus publications concerning responsible AI, safety, and evaluation in health applications.
5. Recent surveys or peer-reviewed studies on LLM agents, memory, orchestration, and healthcare workflows.

Every added reference must be verified through a DOI record, publisher page, proceedings record, official repository, or another authoritative bibliographic source. Unverified or merely plausible references will not be used.

## Chapter 1 Changes

Chapter 1 will receive selective citation support for the scope and function of health coaching; limitations of goal formulation without follow-up, self-monitoring, or feedback; engagement and attrition challenges; continuity and structured state; multi-agent workflow decomposition; and safety and clinical-validation boundaries.

Approximately 4-6 newly introduced sources are expected to appear in Chapter 1. Sources may also appear in Chapter 2 when they support both introductory framing and detailed review.

## Chapter 2 Changes

Chapter 2 will receive the larger share of additions across health-coaching effectiveness and goal review; behavior-change techniques; mobile-health engagement and attrition; conversational-agent effectiveness and safety; LLM health-coaching limitations; longitudinal context and memory; and multi-agent coordination and governance.

Approximately 8-12 newly introduced sources are expected to appear in Chapter 2. The comparative synthesis and research-gap discussion will change only when required by the strengthened evidence.

## Citation Integration Rules

- Use IEEE-style `\cite{key}` citations and the existing BibTeX conventions.
- Attach citations to the specific claims they support.
- Use citation clusters only for genuine synthesis of complementary evidence.
- Distinguish established evidence, design inference, and the dissertation's proposed contribution.
- Avoid claims of clinical effectiveness that exceed the evidence.
- Include DOI fields whenever they exist; otherwise use stable authoritative metadata.
- Preserve the dissertation's established terminology.

## Quality Controls

The revision will check source existence and metadata accuracy; citation-key and BibTeX consistency; undefined keys, duplicate keys, and newly added uncited entries; evidence currency; LaTeX compilation; citation-related build errors; and preservation of the prototype-focused scope.

## Success Criteria

The revision is successful when 12-18 verified references have been added, the principal externally derived claims in Chapters 1 and 2 have proportionate evidence support, the prose remains coherent rather than citation-heavy, and the dissertation compiles without undefined citations or BibTeX errors.
