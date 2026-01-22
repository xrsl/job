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
job query "python"
job export --format csv -o applications.csv
```

**4. Fit Assessment** – AI analyzes how well jobs match your background

```bash
# Assess a job against your CV and experience
job fit 42 --cv cv.pdf --extra persona.md --extra experience.md

# View saved assessments
job fit view --id 1
```

**5. GitHub Integration** – Create issues and post assessments

```bash
# Create GitHub issue from job
job gh issue --id 1 --repo owner/repo

# Post assessment as comment
job gh comment -a 5 --repo owner/repo --issue 12
job gh comment -a 5  # auto-detect repo/issue from job
```

## Job Fit Assessment

Evaluate how well job postings match your background using AI-powered analysis.

### Quick Start

```bash
# 1. Add a job to your database
job add https://example.com/senior-engineer

# 2. Assess fit against your CV
job fit 1 --cv ~/cv.toml

# 3. View the assessment
#    - Overall fit score (0-100)
#    - Matching strengths
#    - Skill/experience gaps
#    - Actionable recommendations
```

### Context Files

Provide your CV with `--cv` and additional context with `--extra/-e`. Both flags accept **any file format** (`.md`, `.toml`, `.txt`, `.pdf`, `.tex`, `.yaml`, `.json`, etc.):

```bash
# CV only
job fit 1 --cv cv.pdf

# CV with extra context files
job fit 1 --cv cv.toml --extra experience.md

# Multiple extra files (any format)
job fit 1 --cv cv.pdf --extra persona.md --extra experience.md --extra paper.pdf

# Using short flag
job fit 1 --cv cv.pdf -e persona.md -e experience.md
```

**Note:** Each file must be provided individually; directory support has been removed.

### Model Selection

Override the default model with `--model` / `-m`:

```bash
job fit 1 --cv cv.toml -m claude-sonnet-4.5
job fit 1 --cv cv.toml -m gemini-2.5-flash
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
job fit del -a 5

# Delete all assessments for a job
job fit del -i 1
```

### Aliases

All fit commands support short aliases:

```bash
job f --id 1 -c cv.toml              # fit
job f v -a 5                         # view
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

## GitHub Integration

Create GitHub issues from job postings and share fit assessments as comments.

### Creating Issues

Convert job postings into GitHub issues for tracking:

```bash
# Create issue from job
job gh issue --id 1 --repo owner/repo
job gh i --url https://example.com/job --repo owner/repo

# Recreate issue (if already posted)
job gh issue --id 1 --repo owner/repo --force
```

**What gets posted:**

- Issue title: `{job.title} at {job.company}`
- Issue body: Full job description with metadata (location, deadline, etc.)
- Job metadata is saved to database (prevents duplicate posting)

### Posting Assessments

Share fit assessments as formatted markdown comments:

```bash
# Post with explicit repo and issue
job gh comment -a 5 --repo owner/repo --issue 12

# Auto-detect from job metadata (if job was posted via 'job gh issue')
job gh comment -a 5

# Mix: auto-detect repo, specify issue
job gh comment -a 5 --issue 12
```

**Comment format includes:**

- Job details with clickable link
- Overall fit score (0-100) with color coding
- Strengths and gaps as bullet lists
- Recommendations and insights
- Collapsible metadata (model, context files, timestamp)

### Workflow Example

```bash
# 1. Add job to database
job add https://example.com/senior-engineer

# 2. Create GitHub issue
job gh issue --id 1 --repo myuser/job-hunt

# 3. Assess fit
job fit 1 --cv cv.toml

# 4. Post assessment (auto-detects repo/issue from step 2)
job gh comment -a 1

# 5. Update CV and reassess
job fit 1 --cv cv.toml

# 6. Post updated assessment
job gh comment -a 2
```

### Aliases

```bash
job gh i --id 1 --repo x/y    # issue
job gh c -a 5                 # comment
```

## Configuration

Create `job.toml` to set defaults for all commands ([tombi VSCode Extension](https://tombi-toml.github.io/tombi/docs/editors/vscode-extension) recommended for schema validation):

```toml
#:schema https://raw.githubusercontent.com/xrsl/job/v0.8.0/schema/schema.json

# Global settings
[job]
model = "gemini-2.5-flash"  # Default AI model
# verbose = true
# db-path = "~/.local/share/job/jobs.db"

# GitHub integration defaults
[job.gh]
repo = "xrsl/cv"  # Default repository for gh commands
# default-labels = ["job-application"]
# auto-assign = true

# Fit assessment defaults
[job.fit]
cv = "~/Documents/cv.md"  # Default CV path
# model = "gemini-2.0-flash-exp"  # Override model for fit
# extra = ["~/Documents/cover-letter.md"]  # Additional context

# Add command defaults
[job.add]
# structured = true  # Always use AI extraction
# browser = false    # Use browser by default
# model = "gemini-2.5-flash"

# Export defaults
[job.export]
# output-format = "json"

# Job search configuration
[job.search]
keywords = ["python", "backend", "senior"]
# parallel = true  # Enable parallel search
# since = 7        # Default --since days

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

### Configuration Precedence

Settings are applied in this order (highest to lowest priority):

1. **CLI flags** – `--repo`, `--model`, `--cv`, `--extra`, etc.
2. **Environment variables** – `JOB_MODEL`, `JOB_DB_PATH`
3. **job.toml** – Config file defaults
4. **Hardcoded defaults** – Built-in fallbacks

### Config File Locations

The CLI searches for `job.toml` in these locations (first found wins):

1. `JOB_CONFIG` environment variable
2. `./job.toml` (current directory)
3. `~/.config/job/job.toml` (XDG config)
4. `~/.job.toml` (home directory)

### Examples

**Use repo from config:**

```bash
# job.toml: [job.gh] repo = "xrsl/cv"
job gh issue --id 2  # Uses xrsl/cv from config
job gh issue --id 2 --repo other/repo  # Override with CLI flag
```

**Use fit defaults:**

```bash
# job.toml: [job.fit] cv = "~/cv.md", extra = ["~/cover.md"]
job fit 1  # Uses cv and extra from config
job fit 1 --extra personal.md  # Merges with config
```

**Use add defaults:**

```bash
# job.toml: [job.add] structured = true, browser = true
job add https://example.com/job  # Uses structured + browser from config
job add https://example.com/job --no-structured  # Override
```

## Environment

| Variable         | Purpose                  | Default                      |
| ---------------- | ------------------------ | ---------------------------- |
| `GEMINI_API_KEY` | AI extraction (required) | –                            |
| `JOB_MODEL`      | Model override           | `gemini-2.5-flash`           |
| `JOB_DB_PATH`    | Database location        | `~/.local/share/job/jobs.db` |
| `JOB_CONFIG`     | Config file path         | `./job.toml`                 |

## Commands

### Job Management

```bash
job search [--company NAME] [--keyword KW] [--extra KW]
job add <url> [--model MODEL] [--no-cache]
job list
job query <query>
job view <url>
job export [--format json|csv] [-o FILE] [--query FILTER]
job info
job del <url>
```

### Fit Assessment

```bash
# Assess fit
job fit <ID> --cv <PATH> [--extra <PATH>] [--model MODEL]

# View assessments
job fit view -i <JOB_ID>          # List all for job
job fit view -a <ASSESSMENT_ID>   # View specific

# Delete assessments
job fit del -a <ASSESSMENT_ID>     # Delete one
job fit del -i <JOB_ID>            # Delete all for job

# Aliases: f (fit), v (view)
job f 1 --cv cv.toml -e persona.md
job f v -a 5
```

### GitHub Integration

```bash
# Create issue from job
job gh issue --id <ID> --repo <OWNER/REPO>
job gh issue --url <URL> --repo <OWNER/REPO>

# Post assessment as comment
job gh comment -a <ASSESSMENT_ID> --repo <OWNER/REPO> --issue <NUM>
job gh comment -a <ASSESSMENT_ID>  # auto-detect repo/issue

# Aliases: i (issue), c (comment)
job gh i --id 1 --repo user/repo
job gh c -a 5
```

### Database

```bash
job db path       # Show database path
job db stats      # Show statistics
job db migrate    # Migrate schema to latest version
job db del        # Delete database
```

## Architecture

**Stack:** Python 3.12+ • Typer • SQLModel • Pydantic AI • Playwright • BeautifulSoup
