# Global Agent Instructions

- Before performing any delete operation, ask the user for confirmation.

## Generated Document Naming

- Save generated documents in the relevant project directory unless the user specifies another location.
- Append `_YYYYMMDD_HHmm` immediately before the file extension, using local time at minute precision.
- Never overwrite an existing generated document. If a same-minute filename exists, append `_02`, `_03`, and subsequent two-digit counters before the extension.

## Dissertation Working Mode

This repository contains an NTU EEE MSc dissertation and the related GoalGuardian/TalkieAI implementation work. Treat dissertation writing as an engineering dissertation rather than a clinical intervention study unless the user later provides real participant data.

### Thesis Positioning

- Position the work as the design, implementation, and prototype-level technical validation of GoalGuardian, a multimodal multi-agent health coaching prototype for weekly SMART goal review.
- Emphasise technical feasibility, system architecture, multi-agent workflow design, session continuity, goal state traceability, memory persistence, dashboard aggregation, and implementation completeness.
- Do not claim clinical effectiveness, behaviour change, improved adherence, user satisfaction, user acceptance, or real-world health impact unless the user provides valid empirical evidence.
- If no formal user study has been conducted, state this explicitly and frame usability work as usability-oriented inspection or task-flow inspection.

### Evaluation Boundary

Use the following evaluation framing by default:

- The evaluation is prototype-level technical validation, not participant-based user research.
- The evaluation can cover functional completeness, task completion, multi-agent workflow verification, session continuity, state traceability, dashboard aggregation, memory persistence, robustness, error handling, and prototype performance observation.
- The evaluation cannot support claims about engagement, health outcomes, clinical safety, long-term adherence, or user satisfaction.
- Future work should include longitudinal user studies, usability questionnaires, qualitative interviews, safety evaluation, and clinical or professional review where appropriate.

### Recommended Chapter 5 Structure

When editing Chapter 5, use this engineering evaluation structure unless the user asks for another structure:

1. Evaluation Scope
2. Functional Completeness Testing
3. Multi-Agent Workflow Verification
4. Interaction Continuity Testing
5. State Traceability Testing
6. Dashboard and Memory Persistence Verification
7. Robustness and Error Handling Checks
8. Prototype Performance Observation
9. Usability-Oriented Inspection
10. Evaluation Summary

### Recommended Chapter 6 Positioning

When editing Chapter 6, conclude that GoalGuardian demonstrates architectural and prototype feasibility. State that the system provides a technically grounded foundation for future empirical validation, but does not yet establish clinical effectiveness or user acceptance.

### Claims to Avoid Without Evidence

Avoid statements such as:

- "The system improved user engagement."
- "Users found the system useful."
- "The system increased goal adherence."
- "User satisfaction was high."
- "The application was validated by users."
- "GoalGuardian improves health outcomes."
- "The system is clinically effective."

Preferred wording:

- "The results demonstrate prototype-level functionality and architectural feasibility."
- "The evaluation focused on technical validation rather than participant-based user research."
- "No formal user study was conducted in this dissertation."
- "The findings should not be interpreted as evidence of behavioural or clinical effectiveness."
- "Future work should evaluate user acceptance, engagement, and goal adherence through longitudinal studies."

## Academic Writing Rules

- Write dissertation content in formal academic English.
- Use third person. Avoid first person expressions such as "I" and "we".
- Use past tense for completed implementation and evaluation work; use present tense for general facts, conclusions, and system descriptions where appropriate.
- Use IEEE citation style with BibTeX keys in the form `\cite{key}`.
- Do not fabricate references, datasets, experiments, participant feedback, numerical results, or user quotes.
- Every external factual claim should be supported by a citation. Every result claim should be supported by implemented system evidence, test output, or clearly labelled observation.
- Keep terminology consistent: use "GoalGuardian", "weekly SMART goal review", "multi-agent system", "MAS", "dashboard aggregation", "session continuity", "state traceability", and "prototype-level technical validation" consistently.

## Project Evidence to Prefer

When grounding claims in existing implementation, prefer evidence from:

- MAS routes and backend APIs.
- Agent service modules for opening, memory, orchestration, goal review, closing, and summary synthesis.
- Dashboard aggregation services.
- Goal state event handling.
- MAS memory store and persistence support.
- Existing automated tests for dashboard behaviour, memory store behaviour, mobile manifest configuration, database configuration, and service import behaviour.
- Existing dissertation chapters and LaTeX sources under `ntu-dissertation/latex/`.

## LaTeX Workflow

- Main dissertation source is under `ntu-dissertation/latex/`.
- Main file is `ntu-dissertation/latex/main.tex`.
- Chapter files are under `ntu-dissertation/latex/chapter-*`.
- Bibliography is `ntu-dissertation/latex/c-back-matter/references.bib`.
- Compile with the available LaTeX toolchain and report whether compilation succeeded.
- If compilation generates warnings but produces a PDF, distinguish non-blocking warnings from errors.

