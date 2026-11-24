# Job Finder for Claude

**A personal job-search assistant for any profession** (engineers, designers, QA, product owners, and more).
It learns what you want in a short chat, finds fresh jobs you can actually take, writes a **truthful** CV
tailored to each one, and prepares a one-click apply kit. **You** review and apply. It never applies or contacts
anyone for you.

- Finds jobs on companies' own career pages (free public job boards), plus links you paste
- Checks each job: recent? not a repost? can you legally take it from where you live? pay above your floor?
- Scores each match and explains the gaps honestly
- Builds a one-page CV from **your** approved CV: reordered and reworded, never invented
- Each job gets a folder with your CV (PDF + Word), notes, and an apply kit: double-click, attach, submit
- Keeps a tracker of what you found and applied to
- Your data stays in a folder on your own computer

## Install (Claude Desktop, no technical skills needed)

**👉 Step-by-step guide with pictures-in-words: [docs/INSTALL.md](docs/INSTALL.md)**

Short version:
1. In the Claude desktop app, open **Customize → Plugins → Add → Add marketplace**, and paste
   `https://github.com/YoadBarok/job-finder`. Then add **Job Finder**.
2. Create a folder called **Job search** (e.g. in Documents) and connect it in a chat with **Add folder**.
3. Say: **"Help me find a job"**. Job Finder interviews you and asks for your current CV.

No plugins option? Download [`dist/job-finder-skill.zip`](dist/job-finder-skill.zip) and upload it under
**Customize → Skills → + → Upload a skill**.

## Claude Code users

```
/plugin install job-finder --marketplace YoadBarok/job-finder
```
Then say "set me up", or use `/job-finder:setup`, `/job-finder:find`, `/job-finder:tailor <link>`, `/job-finder:digest`.
Or clone this repo and run `claude` in it: the skills load from `.claude/skills`.

## What it will and won't do

| Will | Won't |
|---|---|
| Rephrase and reorder your real experience for each job | Invent skills, titles, dates, numbers or degrees |
| List anything it isn't sure is true and ask you once | Apply, submit forms, or message anyone |
| Check where you're allowed to work before suggesting a job | Automate your LinkedIn account |
| Use free public job feeds and web search | Spend money unless you approve each paid search |

Always read your CV before you send it. You're responsible for what you submit.

## Privacy

Your CV, preferences, form answers and job folders live **only** in the folder you choose on your computer.
The plugin itself contains no personal data. Job searches read public job-board pages. During setup it looks for
an existing Job Finder folder by reading only the first line of files named `criteria.md` in common places.
Claude processes your data like any other conversation with Claude. Details: [SECURITY.md](SECURITY.md).

## For developers

- Plugin: `plugins/job-finder/` (skills, scripts, templates, references). Marketplace: `.claude-plugin/marketplace.json`.
- Tests: `npm test` (Python unittest + Node; synthetic data only).
- After changing the plugin, rebuild the standalone skill: `python3 dev/build_skill_zip.py` (a test checks it).
- Validate: `claude plugin validate .`

Not affiliated with Anthropic. MIT licensed.
