# Team Procedures

This repository contains the source for the Team Procedures documentation site, built with MkDocs Material and published to GitHub Pages.

## Local setup

Create a virtual environment and install the pinned dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Preview the site locally:

```powershell
.venv\Scripts\python.exe -m mkdocs serve
```

Run the same validation used in continuous integration:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m mkdocs build --strict
```

## Add a procedure

1. Add the Markdown file under the appropriate topic in `docs/`.
2. Include the required front matter shown below, using ISO `YYYY-MM-DD` dates.
3. Add the page to the topic navigation in `mkdocs.yml`.
4. Run the tests and strict build before opening a pull request.

```yaml
---
document_id: SOP-XXX-001
title: Example Procedure
topic: Field sampling
version: "1.0"
owner: Responsible Team
last_reviewed: 2026-01-15
next_review_due: 2027-01-15
---
```

The home-page catalogue is generated automatically from procedure front matter. Every procedure page receives a document-control panel from the same metadata. A procedure becomes overdue on the day after `next_review_due`, based on the local date in Western Australia.

Write page content and generated interface labels in Australian English. Source dates remain in ISO format; displayed dates use day-month-year order, for example `15 January 2026`.

## GitHub Pages

The `Build and deploy documentation` workflow validates pull requests and publishes pushes to `main` or manually dispatched runs. It uploads the generated `site/` directory as a Pages artifact and deploys it with the official GitHub Pages actions; it does not use a `gh-pages` branch.

For the first deployment, open the repository's **Settings > Pages** and set **Source** to **GitHub Actions**.