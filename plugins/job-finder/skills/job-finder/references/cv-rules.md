# CV rules

- **Truth only.** Sources of facts: `base/cv.base.json`, background files named in criteria.md, and
  `## Confirmed facts`. Tailoring = choosing, ordering and rephrasing true things. Never invent employers,
  titles, dates, degrees, tools, skills, numbers or outcomes. A requirement they lack → "gap" in notes.
- **Designed vs built vs released.** Write exactly what's true ("designed", "building", "launched"). If a
  background file is ambiguous, ask, then record the answer in Confirmed facts.
- **List every new claim** (not in base CV or Confirmed facts) under "Needs your confirmation" in notes.md.
- **Keep the base layout and length** (one page if the base is one page). Fit by cutting words, not by
  shrinking text. Standard headings, single column, ATS-readable.
- **Headline:** the target role's title if criteria.md says so. Job titles and dates in the history stay exactly as in the base.
- **Identity rules** in criteria.md (how to describe them, how never to) apply to the profile text too.
- **No hyperlinks** anywhere; contact details are plain text. File name `<First> <Last> CV.pdf`.
- **Confidentiality:** nothing from `forbidden_terms.txt`; no employer-internal names, ticket IDs or codenames.
  Public product names, open standards and common tools are fine.
- **Voice:** outcome-first, specific, no filler. Match the field: designers show process and impact, QA shows
  quality outcomes and automation, product people show decisions and results.
- **Checks:** check_cv.py must print OK (1 page, no links, no forbidden terms, not template, ATS text order).
  Look at the rendered page. Keyword gaps it lists are gaps, not instructions to add words.
