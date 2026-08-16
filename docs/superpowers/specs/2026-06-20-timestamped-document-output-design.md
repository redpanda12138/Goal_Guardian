# Timestamped Document Output Design

## Objective

Generate the dissertation PDF in the dissertation project root with a timestamped filename, and record the naming convention in the global Codex `AGENTS.md` so future document-generation tasks follow the same rule.

## Output

- Source: `ntu-dissertation/latex/main.tex`
- Destination directory: `ntu-dissertation/`
- Filename: `GoalGuardian_Dissertation_YYYYMMDD_HHmm.pdf`
- Time basis: local Asia/Shanghai time
- Precision: one minute

## Generation Flow

1. Compile the complete LaTeX project with bundled Tectonic in a system temporary directory.
2. Require a successful compiler exit code and a generated PDF.
3. Copy only the final PDF into the dissertation project root using the timestamped filename.
4. Leave intermediate LaTeX files outside the project directory.

## Collision Handling

If the timestamped filename already exists, do not overwrite it. Append `_02`, `_03`, and subsequent two-digit counters before `.pdf` until an unused filename is found.

## Global Rule

Update `C:\Users\86130\.codex\AGENTS.md` with these instructions:

- Save generated documents in the relevant project directory unless the user specifies another location.
- Append `_YYYYMMDD_HHmm` immediately before the file extension.
- Use local time at minute precision.
- Never overwrite an existing generated document; append `_02`, `_03`, and so on for same-minute collisions.

These rules apply to generated documents generally, including PDF, DOCX, PPTX, and spreadsheet deliverables.

## Verification

- Confirm the global `AGENTS.md` contains the complete convention.
- Confirm compilation exits successfully.
- Confirm the timestamped PDF exists in `ntu-dissertation/`.
- Confirm the file is non-empty and begins with the PDF signature.
- Confirm no existing document was overwritten or deleted.
