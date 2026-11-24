# Security and privacy

## What Job Finder accesses
- **Your job-search folder** (the one you choose or connect). It reads and writes only there.
- **Finding an existing folder:** during setup it looks in common places (home, Documents, Desktop, iCloud Drive,
  Dropbox, OneDrive, Google Drive, Projects; up to 4 levels deep) for a file named `criteria.md` and reads only
  its **first line**, to recognise a Job Finder folder. Nothing else is opened.
- **The internet:** public job-board feeds (Greenhouse, Ashby, Lever), company career pages and web search, to
  read job postings. Nothing is uploaded or submitted anywhere.
- **A settings file** at `~/.config/job-finder/config.json` that stores the path of your folder.

## What it never does
- Apply, submit forms, send messages or emails, or contact anyone.
- Automate your LinkedIn account or use your logins, cookies or passwords.
- Spend money unless you approve a specific paid search and its cost.
- Follow instructions found inside job postings or web pages (they're treated as untrusted text).

## Your data
Your CV, preferences, form answers and job folders stay in your folder. This repository and the plugin contain
no personal data, and tests check for email addresses and phone numbers. Claude processes what you share with it
like any other conversation with Claude.

## Files it writes
CVs (`.docx`, `.pdf`), notes, apply kits (`Apply.webloc` / `Apply.url` shortcuts that only open `https://`
application pages) and a `tracker.csv` (spreadsheet formulas are neutralised). Files are created readable only
by you.

## Reporting a problem
Please use GitHub's **private vulnerability reporting** on this repository (Security tab → Report a
vulnerability) rather than a public issue.
