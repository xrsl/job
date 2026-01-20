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

**4. Fit Assessment** – AI analyzes how well jobs match your background

```bash
# Assess a job against your CV and experience
job fit --id 1 --context cv.toml --context reference/

# View saved assessments
job fit view --id 1

# Post assessment to GitHub issue
job fit post -a 5 --issue 45 --repo owner/repo
```

## Job Fit Assessment

Evaluate how well job postings match your background using AI-powered analysis.

### Quick Start

```bash
# 1. Add a job to your database
job add https://example.com/senior-engineer

# 2. Assess fit against your CV
job fit --id 1 --context ~/cv.toml

# 3. View the assessment
#    - Overall fit score (0-100)
#    - Matching strengths
#    - Skill/experience gaps
#    - Actionable recommendations
```

### Context Files

The `--context` flag accepts **any file format**:
- **Individual files**: `.md`, `.toml`, `.txt`, `.pdf`, `.tex`, `.yaml`, `.json`, etc.
- **Directories**: Recursively reads all files (UTF-8 text files; skips binaries)
- **Multiple paths**: Mix files and directories

```bash
# Single file (any format)
job fit --id 1 --context cv.toml
job fit --id 1 --context resume.pdf

# Multiple files (mixed formats)
job fit --id 1 --context cv.toml --context experience.md --context paper.pdf

# Directory (recursive, all files)
job fit --id 1 --context reference/

# Mix of both
job fit --id 1 --context cv.toml --context reference/ --context resume.pdf
```

**Note:** Binary files in directories are automatically skipped with a warning.

### Model Selection

Override the default model with `--model` / `-m`:

```bash
job fit --id 1 --context cv.toml -m claude-sonnet-4.5
job fit --id 1 --context cv.toml -m gemini-2.5-flash
```

### Managing Assessments

**View assessments:**

```bash
# View specific assessment
job fit view -a 5

# List all assessments for a job (interactive selection)
job fit view -i 1

# View specific assessment for a job
job fit view -i 1 -a 5
```

**Delete assessments:**

```bash
# Delete specific assessment
job fit rm -a 5

# Delete all assessments for a job
job fit rm -i 1
```

**Post to GitHub:**

Share assessments as formatted comments on GitHub issues:

```bash
# Post assessment to issue
job fit post -a 5 --issue 45 --repo owner/repo

# The comment includes:
# - Job details with clickable link
# - Fit score and summary
# - Strengths and gaps as bullet lists
# - Recommendations and insights
# - Collapsible metadata (model, context files, timestamp)
```

### Aliases

All fit commands support short aliases:

```bash
job f --id 1 -c cv.toml              # fit
job f v -a 5                         # view
job f p -a 5 --issue 45 --repo x/y   # post
```

### Assessment Output

Each assessment includes:

1. **Overall Fit Score** (0-100)
   - 80-100: Excellent match
   - 60-79: Good match
   - 40-59: Moderate match
   - 0-39: Poor match

2. **Fit Summary** – 2-3 sentence overview

3. **Strengths** – Specific qualifications that match well

4. **Gaps** – Missing qualifications or areas of concern

5. **Recommendations** – Actionable advice to strengthen your application

6. **Key Insights** – Notable observations (timing, unique angles, red flags, opportunities)

### Storage

Assessments are stored in the database with:
- Job reference
- Model used
- Context files used
- Timestamp
- Full assessment details

This allows you to:
- Track how your fit changes as you update your CV
- Compare assessments from different models
- Maintain a history of all job evaluations

## Configuration

Create `job-search.toml` with schema validation ([tombi VSCode Extension](https://tombi-toml.github.io/tombi/docs/editors/vscode-extension) recommended):

```toml
#:schema https://raw.githubusercontent.com/xrsl/job/v0.5.0/schema/schema.json

[job.search]
keywords = ["python", "backend", "senior"]

[[job.search.in]]
company = "Spotify"
url = "https://lifeatspotify.com/jobs"

[[job.search.in]]
company = "Linear"
url = "https://linear.app/careers"
keywords = ["typescript", "react"]  # Override defaults

[[job.search.in]]
company = "Stripe"
url = "https://stripe.com/jobs/search"
extra-keywords = ["fintech", "payments"]  # Merge with defaults
```

## Environment

| Variable            | Purpose                  | Default                      |
| ------------------- | ------------------------ | ---------------------------- |
| `GEMINI_API_KEY`    | AI extraction (required) | –                            |
| `JOB_MODEL`         | Model override           | `gemini-2.5-flash`           |
| `JOB_DB_PATH`       | Database location        | `~/.local/share/job/jobs.db` |
| `JOB_SEARCH_CONFIG` | Config file path         | `./job-search.toml`          |

## Commands

### Job Management

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

### Fit Assessment

```bash
# Assess fit
job fit --id <ID> --context <PATH> [--model MODEL]
job fit --url <URL> --context <PATH>

# View assessments
job fit view -i <JOB_ID>          # List all for job
job fit view -a <ASSESSMENT_ID>   # View specific

# Delete assessments
job fit rm -a <ASSESSMENT_ID>     # Delete one
job fit rm -i <JOB_ID>            # Delete all for job

# Post to GitHub
job fit post -a <ID> --issue <NUM> --repo <OWNER/REPO>

# Aliases: f (fit), v (view), p (post)
job f -i 1 -c cv.toml
job f v -a 5
job f p -a 5 --issue 45 --repo user/repo
```

## Architecture

**Stack:** Python 3.12+ • Typer • SQLModel • Pydantic AI • Playwright • BeautifulSoup
