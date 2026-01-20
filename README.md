# Job CLI

**AI-powered job hunting automation.** Scrape career pages, extract structured data, track applications.

## Installation

```bash
uv tool install git+https://github.com/xrsl/job.git
```

## What It Does

**1. Discovery** – Monitor career pages for keywords

```bash
job search --company spotify --keyword "senior backend"
```

**2. Extraction** – AI extracts structured data from job postings

```bash
job add https://spotify.com/careers/backend-engineer
# → Parses title, location, deadline, full description
```

**3. Tracking** – Query and export your job pipeline

```bash
job find "python"
job export --format csv -o applications.csv
```

## Configuration

Create `job-search.toml` with schema validation ([tombi VSCode Extension](https://tombi-toml.github.io/tombi/docs/editors/vscode-extension) recommended):

```toml
#:schema https://raw.githubusercontent.com/xrsl/job/v0.2.0/schema/schema.json

[job.search]
keywords = ["python", "backend", "senior"]

[[job.search.in]]
company = "Spotify"
link = "https://lifeatspotify.com/jobs"

[[job.search.in]]
company = "Linear"
link = "https://linear.app/careers"
keywords = ["typescript", "react"]  # Override defaults
enabled = true  # Set false to disable
```

## Environment

| Variable            | Purpose                  | Default                      |
| ------------------- | ------------------------ | ---------------------------- |
| `GEMINI_API_KEY`    | AI extraction (required) | –                            |
| `JOB_MODEL`         | Model override           | `gemini-2.5-flash`           |
| `JOB_DB_PATH`       | Database location        | `~/.local/share/job/jobs.db` |
| `JOB_SEARCH_CONFIG` | Config file path         | `./job-search.toml`          |

## Commands

```bash
job search [--company NAME] [--keyword KW] [--extra KW]
job add <url> [--model MODEL] [--no-cache]
job list
job find <query>
job show <url>
job export [--format json|csv] [-o FILE] [--query FILTER]
job info
job rm <url>
```

## Architecture

**Stack:** Python 3.12+ • Typer • SQLModel • Pydantic AI • Playwright • BeautifulSoup
