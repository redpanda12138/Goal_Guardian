# Chapters 1--2 Revision Log

This log records the revisions made in response to the supplied comments and the independent sub-agent audit.

| # | Comment or audit finding | Action taken | Status |
|---|---|---|---|
| 1 | Objective 1 omitted non-functional requirements | Added functional and non-functional requirements in Chapter 1 and aligned Chapter 3 | Resolved |
| 2 | RQ4 asked how to evaluate rather than what the evaluation demonstrates | Reframed RQ4 around functional completeness, task completion, interaction continuity, system traceability, and usability | Resolved |
| 3 | Research questions lacked chapter mapping | Added an RQ1--RQ4 mapping paragraph after the research questions | Resolved |
| 4 | Multimodality claim required caution | Described the implemented speech-to-text path as a prototype that is not clinically validated; aligned Chapters 1, 2, and 6 | Resolved |
| 5 | Chapter 2 introduction used a brittle topic count | Replaced the fixed count with several interconnected areas and included multimodality and responsible AI | Resolved |
| 6 | Table reference could render as ?Table Table 2.1? | Removed the manual type name because the template includes ?Table? in `\thetable`; applied the same correction in Chapter 5 | Resolved |
| 7 | Table 2.1 was crowded | Rotated the complete table using the existing `graphicx` dependency, shortened cells, added longitudinal continuity, normalised Yes/Partial/No, and simplified the GoalGuardian row label | Resolved |
| 8 | Comparative Synthesis and Research Gap must remain distinct | Preserved the two-section structure and their analytical/gap functions | Resolved |
| 9 | MAS limitations needed stronger critical analysis | Added coordination latency, context duplication, inconsistent outputs, cascading failures, and implementation/maintenance cost | Resolved |
| 10 | Bloom, MAS, and GoalGuardian roles needed clearer differentiation | Identified Bloom as the interaction-design reference, the MAS paper as the workflow-architecture reference, and GoalGuardian as an operationalisation contribution rather than a new behaviour-change theory | Resolved |
| 11 | Chapters 3--6 remain drafts | Changed the Chapter 5 description to evaluation protocol and planned result reporting; no empirical results were invented | Resolved |
| 12 | Evaluation dimensions differed across chapters | Aligned the abstract and Chapters 1, 3, 5, and 6 on the same five dimensions | Resolved |
| 13 | British-English usage was inconsistent | Normalised generic prose while retaining official names such as Behavior Change Technique Taxonomy and Summarization Agent | Resolved |
| 14 | Template placeholders remain | Retained them as requested for the current draft; corrected the Appendix A/B TOC parentheses | Deferred to final submission |

## Verification

- Static consistency check: 0 errors.
- Tectonic compilation: exit code 0, 64 pages.
- Remaining messages: underfull-box and font warnings only; no LaTeX error or overfull-box failure.
- Independent sub-agent re-review: no remaining actionable findings in the reviewed scope.
