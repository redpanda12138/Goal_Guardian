# Timestamped Dissertation PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a complete timestamped dissertation PDF in the dissertation project root and persist the minute-precision naming convention in the global Codex instructions.

**Architecture:** Compile `main.tex` with bundled Tectonic into a system temporary directory, then copy only the verified PDF into the dissertation root using a collision-safe timestamped name. Update the existing global `AGENTS.md` additively so its delete-confirmation rule is preserved.

**Tech Stack:** PowerShell, LaTeX/Tectonic, BibTeX, global Codex `AGENTS.md`, and filesystem signature checks.

---

### Task 1: Preserve and extend the global instructions

**Files:**
- Modify: `C:\Users\86130\.codex\AGENTS.md`

- [ ] **Step 1: Read the existing global instructions**

Run:
```powershell
Get-Content -Raw -LiteralPath 'C:\Users\86130\.codex\AGENTS.md'
```

Expected: the existing rule requiring confirmation before delete operations remains present.

- [ ] **Step 2: Append the document-output convention without replacing existing rules**

Add these rules:
```markdown
## Generated Document Naming

- Save generated documents in the relevant project directory unless the user specifies another location.
- Append `_YYYYMMDD_HHmm` immediately before the file extension, using local time at minute precision.
- Never overwrite an existing generated document. If a same-minute filename exists, append `_02`, `_03`, and subsequent two-digit counters before the extension.
```

- [ ] **Step 3: Verify both instruction groups**

Run:
```powershell
Get-Content -Raw -LiteralPath 'C:\Users\86130\.codex\AGENTS.md'
```

Expected: the delete-confirmation rule and all three generated-document rules are present exactly once.

### Task 2: Compile the complete dissertation

**Files:**
- Build: `ntu-dissertation/latex/main.tex`
- Temporary output: `%TEMP%\codex-ntu-latex-timestamped\main.pdf`

- [ ] **Step 1: Create the temporary output directory**

Run:
```powershell
$tempBuild = Join-Path $env:TEMP 'codex-ntu-latex-timestamped'
New-Item -ItemType Directory -Path $tempBuild -Force
```

Expected: the directory exists; no existing files are deleted.

- [ ] **Step 2: Compile with UTF-8 logging and bundled Tectonic**

Run from `C:\Users\86130\.codex\plugins\cache\openai-bundled\latex\0.2.3`:
```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
python scripts/compile_latex.py 'D:\SECOND WINDOW\NTU_Project\Dissertation\chatgpt-talkieai-main\ntu-dissertation\latex\main.tex' --compiler tectonic --output-directory $tempBuild --json
```

Expected: exit code 0, `pdfExists: true`, and a complete PDF generated from all six chapters and the BibTeX bibliography.

### Task 3: Select a collision-safe project filename

**Files:**
- Create: `ntu-dissertation/GoalGuardian_Dissertation_YYYYMMDD_HHmm.pdf`

- [ ] **Step 1: Generate the minute timestamp**

Run:
```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmm'
$projectRoot = 'D:\SECOND WINDOW\NTU_Project\Dissertation\chatgpt-talkieai-main\ntu-dissertation'
$candidate = Join-Path $projectRoot ("GoalGuardian_Dissertation_${stamp}.pdf")
```

Expected: the filename contains the local timestamp immediately before `.pdf`.

- [ ] **Step 2: Resolve same-minute collisions**

Run:
```powershell
$counter = 2
while (Test-Path -LiteralPath $candidate) {
    $candidate = Join-Path $projectRoot ("GoalGuardian_Dissertation_${stamp}_{0:D2}.pdf" -f $counter)
    $counter++
}
```

Expected: `$candidate` does not exist, so no existing document can be overwritten.

### Task 4: Copy and verify the final PDF

**Files:**
- Read: `%TEMP%\codex-ntu-latex-timestamped\main.pdf`
- Create: collision-safe PDF path selected in Task 3

- [ ] **Step 1: Copy only the compiled PDF**

Run:
```powershell
Copy-Item -LiteralPath (Join-Path $tempBuild 'main.pdf') -Destination $candidate
```

Expected: one new timestamped PDF appears in `ntu-dissertation/`; no existing file is changed or deleted.

- [ ] **Step 2: Verify file size and PDF signature**

Run:
```powershell
$file = Get-Item -LiteralPath $candidate
$bytes = [System.IO.File]::ReadAllBytes($candidate)
$signature = [System.Text.Encoding]::ASCII.GetString($bytes[0..3])
[pscustomobject]@{Path=$file.FullName; Bytes=$file.Length; Signature=$signature; Modified=$file.LastWriteTime}
```

Expected: byte length is greater than zero and signature equals `%PDF`.

- [ ] **Step 3: Confirm the timestamp convention and final location**

Run:
```powershell
$file.Name -match '^GoalGuardian_Dissertation_\d{8}_\d{4}(_\d{2})?\.pdf$'
```

Expected: `True`.
