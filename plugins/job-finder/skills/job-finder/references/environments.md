# Working in different places

## Claude Code (terminal or Code tab)
Scripts run locally. Use `python3 SCRIPTS/doctor.py --json` at the start. If the data folder is outside the
project, ask the person to type `/add-dir <path>` once (or configure.py `--claude-settings .claude/settings.local.json`).

## Claude app with a connected folder (chat or Cowork)
- The person's files stay in the connected folder on their computer. If your file tools can open that folder
  directly, work there. If you only reach it by copying files (stage in, commit out), copy in only what a step
  needs (criteria.md, search.json, base/cv.base.json, apply_profile.json, the job's files), run the scripts in
  your workspace with `--data <your local copy>`, and copy results back into `jobs/<folder>/`, `tracker.csv`,
  `seen.json` and `candidates/`.
- Never open other folders on their computer.
- Scripts need Python 3 and Node with the `docx` library; LibreOffice for PDFs. If something's missing in your
  workspace, use your own document tools to produce the same .docx and .pdf, following cv-rules.md.
- If your workspace can't reach the job-board feeds, use web fetch on the same URLs.

## No folder at all (e.g. phone or web without the desktop app)
Explain that Job Finder keeps their CV and job list in a folder on their computer, and ask them to open the
Claude desktop app and connect one. Until then, you can still review a pasted job description against a CV
they attach, but don't run setup.
