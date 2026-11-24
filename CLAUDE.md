# Job Finder (repo)

This repo is the **Job Finder** Claude plugin (`plugins/job-finder/`) plus its marketplace (`.claude-plugin/`).
The skills are also linked into `.claude/skills/`, so a Claude Code session in this folder can use them directly.

## If the user wants to search for jobs
Use the `job-finder` skill (`plugins/job-finder/skills/job-finder/SKILL.md`) and follow it exactly. Its scripts
are in that skill's `scripts/` folder. First run `python3 plugins/job-finder/skills/job-finder/scripts/doctor.py --json`;
if it isn't ok, guide setup (the skill's `references/setup.md`) before anything else, even if they asked for jobs.
Personal data lives outside this repo in the folder the doctor resolves; never copy personal data into the repo.

## If the user wants to change Job Finder itself
- Edit files under `plugins/job-finder/`. Keep `SKILL.md` lean; details go in `references/`.
- Run `npm test` and `claude plugin validate .`, then `python3 dev/build_skill_zip.py` (a test checks the zip is current).
- Bump `version` in `plugins/job-finder/.claude-plugin/plugin.json` for each release, so installed users get updates.

## Hard rules
Never apply or contact anyone for the user · never invent CV facts · no hyperlinks in CVs · CV file is
`<First> <Last> CV.pdf` · ask before spending money or installing anything · don't automate LinkedIn.
