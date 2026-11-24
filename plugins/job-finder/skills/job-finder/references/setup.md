# Setup (first run, or when the data folder is new or still templates)

Goal: in about 10 minutes of conversation, the data folder holds the person's real preferences, an approved
base CV and their form answers. Ask in small groups, in plain language, and propose sensible defaults. Don't
show file names. Never write "TBD" and move on: the readiness check treats it as unfinished.

## Step 1: the folder
- **Ask first:** "Have you used Job Finder before, for example on another computer? Do you already have a
  job-search folder?" The readiness check lists folders it found. If one is theirs, use it and skip the
  interview parts it already covers. Never re-interview over existing data.
- New person: Claude Code → `python3 SCRIPTS/configure.py --data <path>` (suggest `~/job-finder-data`, or a
  synced folder such as iCloud or Dropbox to share across computers), then ask them to type `/add-dir <path>`
  once. Claude app → they create a folder (e.g. "Job search" in Documents) and connect it with **Add folder**;
  copy the files from `templates/` into it (`templates/cv.json` → `base/cv.base.json`), then create an empty
  `jobs/` folder and a `tracker.csv` with the header `company,role,link,score,date_found,source,cost_usd,status,updated,note`.
- Claude Code may also need: `npm install --prefix ~/.cache/job-finder docx`, LibreOffice and Poppler.
  Explain each in one line and ask before installing anything.

## Step 2: the interview → criteria.md, search.json, apply_profile.json
1. **Their CV first.** Ask them to attach or drop their latest CV (PDF or Word). Read it; it answers many later questions.
2. **Who and where:** name, city/country, time zone (UTC offset), citizenships and residence or work permits.
   From that, write `authorized` in search.json: the countries/regions where they can be employed directly
   (EU citizens → "EU"; US citizens or green-card holders → "United States", and so on). Ask whether they'd
   take contractor or employer-of-record roles in other countries (`contractorOK`). Ask which languages they can
   work in (→ `languages`; jobs that require another one are marked down and flagged, not hidden).
3. **What they want:** profession and target titles (e.g. "Senior Product Designer", "QA Automation Engineer",
   "Product Owner"), seniority, titles to avoid, **remote only, or also hybrid / on-site, and in which cities**
   (→ `workplaces` and `commuteCities` in search.json; hybrid/on-site roles are kept only in those cities), must-haves,
   deal-breakers, tools they love and ones they don't know, industries or companies to prefer or avoid.
   Put the role words in `titleRequireAny` (they also earn the title score). For rare or very senior roles
   (creative director, head of X, principal) few jobs appear each week: suggest `maxAgeDays` 30–45 instead of 14.
4. **Pay floor** with currency and period. Say they can skip it.
5. **How many jobs** per day or week, and a minimum score (default 70).
6. **CV preferences:** headline = target role title? How to describe them, and how never to (e.g. "never call
   me junior"). A4 or US Letter.
7. **Confidential names:** internal names from their employers (project codenames, internal tools, ticket
   prefixes) that must never appear → `forbidden_terms.txt`. Fine if there are none.
8. **Form answers** → `apply_profile.json`: email, phone, LinkedIn, portfolio/GitHub/website, work
   authorization answers, notice period.
9. **Paid job sources:** off unless they want them (explain cost first).

Translate (3) into search.json: `titleRequireAny` (patterns a title must contain, e.g. "designer", "qa|quality|test",
"product owner|product manager"), `titleInclude` (strong-fit words), `titleExclude`, `strongKeywords` (domain
words), `stackKeywords` (tools). Set `homeCountry`, `homeUtcOffset`, `authorized`, `contractorOK`, `workplaces`
(any of "remote", "hybrid", "onsite") and `commuteCities`.

**Companies:** the starter list in `config/companies.json` is mostly tech companies, which also hire designers,
QA and product people. Ask about their field and region, propose 15–30 more companies known to hire remotely
in it, check their job board (Greenhouse/Ashby/Lever/Workable/Recruitee/Personio; see sourcing.md), and save the full list as
`companies.json` in the data folder.

## Step 3: the base CV
Rebuild their CV **word for word** as `base/cv.base.json` (see templates/cv.json; extra sections such as
education, projects, languages, certifications or portfolio go in `sections`). Fix only what they ask. Build
it with build_cv.js and to_pdf.py, **show it to them, and get explicit approval**. Save their original PDF as
`base/base.pdf`. Record in criteria.md: "Base CV approved on <date>".

## Step 4: done
Run the readiness check again (or re-read the folder in the app). Then summarise their setup in 5 lines and
offer a first search.
