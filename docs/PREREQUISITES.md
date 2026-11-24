# Prerequisites and integrations

You don't need to read this: Job Finder checks all of it and walks you through what's missing.
In the Claude desktop app nothing needs installing (see [INSTALL.md](INSTALL.md)). This page is the reference for Claude Code.

## Required

| What | Why | Install (macOS) |
|---|---|---|
| Claude Code | runs the agent | https://claude.com/claude-code, then `/plugin install job-finder --marketplace YoadBarok/job-finder` |
| Python 3.10+ | job search, checks, apply kit, tracker | `brew install python` |
| Node.js 18+ and the `docx` library | CV builder | `brew install node`, then `npm install --prefix ~/.cache/job-finder docx` |
| LibreOffice (`soffice`) | .docx to .pdf | `brew install --cask libreoffice`. If `soffice` isn't on PATH: `ln -s /Applications/LibreOffice.app/Contents/MacOS/soffice /usr/local/bin/soffice` |
| Poppler (`pdftotext`, `pdftoppm`) | CV checks and rendering | `brew install poppler` |
| A private data folder | your criteria, base CV, form answers, jobs, tracker | setup asks where (remembered in `~/.config/job-finder/config.json`); in Claude Code you type `/add-dir <path>` once |
| Filled-in data | the agent works for *you* | `/setup` in Claude Code (an interview, plus your CV PDF) |

## Optional integrations

### Apify (paid job sources)
Only useful when the free poller and pasted links aren't enough. In our tests, the remote-jobs Actors
were weak for people outside the US. Costs apply per result; the agent asks before every run.

1. Apify account: https://console.apify.com/sign-up (the free plan includes monthly credit)
2. In Claude Code: `/plugin install apify` (if not found: `/plugin marketplace add apify/apify-claude-code-plugin`, then `/plugin install apify@apify`)
3. `/mcp`, then `plugin:apify:apify`, then **Enable**, then **Authenticate** (browser OAuth, then Allow access)
4. Headless or SSH machine: create an API token in Apify Console and `export APIFY_TOKEN=...` before starting Claude Code

Source: https://docs.apify.com/integrations/claude-code-cli

### LinkedIn
Nothing to connect. LinkedIn's terms forbid automated access, and the agent never handles your cookies
or session. Paste job links or descriptions instead. LinkedIn job pages usually block automated fetches,
so the description itself is best. Browser automation of your account stays off unless you explicitly
allow it in `criteria.md`.

### GitHub (only for changing the agent itself)
Not needed to use the agent. Needed only if Claude should commit and push changes to your fork.
