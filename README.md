# Job CLI

AI-powered job hunting automation. Scrape career pages, extract structured data, track applications.

## Installation

```bash
uv tool install git+https://github.com/xrsl/job.git
```

## Quick Start

```bash
# Search career pages
job search --company spotify --keyword "senior backend"

# Add job with AI extraction
job add --structured https://spotify.com/careers/backend-engineer

# Assess fit against your CV
job fit 1 --cv cv.toml --extra experience.md

# Generate tailored CV + cover letter
job app write 1 --cv cv.toml --letter letter.toml

# Track in GitHub
job gh issue -f 1 --repo owner/repo
job gh comment -a 1
```

## Commands

| Command | Description |
|---------|-------------|
| `job search` | Monitor career pages for keywords |
| `job add <URL>` | Add job posting (use `--structured` for AI extraction) |
| `job list` / `job query` | Browse and search saved jobs |
| `job fit <ID>` | AI fit assessment against your CV |
| `job app write <ID>` | Generate tailored CV and cover letter |
| `job gh issue` / `job gh comment` | GitHub integration |
| `job db stats` | Database info |

## Configuration

Create `job.toml` for defaults:

```toml
#:schema https://raw.githubusercontent.com/xrsl/job/v0.9.0/schema/schema.json

[job]
model = "gemini-2.5-flash"

[job.gh]
repo = "user/job-hunt"

[job.fit]
cv = "~/cv.toml"

[job.app]
cv = "~/cv.toml"
letter = "~/letter.toml"

[[job.search.in]]
company = "Spotify"
url = "https://lifeatspotify.com/jobs"
```

Config locations: `./job.toml` → `~/.config/job/job.toml` → `~/.job.toml`

## Environment

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | AI extraction (required) |
| `JOB_MODEL` | Model override |
| `JOB_DB_PATH` | Database location |

## Architecture

Python 3.12+ • Typer • SQLModel • Pydantic AI • Playwright • BeautifulSoup
