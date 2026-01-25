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
job add --structured https://spotify.com/careers/backend-engineer
# → Parses title, location, deadline, full description
```

**3. Tracking** – Query and export your job pipeline

```bash
job query "python"
job export -o jobs.json
```

**4. Fit Assessment** – AI analyzes how well jobs match your background

```bash
# Assess a job against your CV and experience
job fit 42 --cv cv.pdf --extra experience.md --extra letter.toml

# View saved assessments
job fit view 1
```

**5. GitHub Integration** – Create issues and post assessments

```bash
# Create GitHub issue from job
job gh issue -f 1 --repo owner/repo

# Post assessment as comment
job gh comment -a 5 --repo owner/repo --issue 12
job gh comment -a 5  # auto-detect repo/issue from job
```

**6. Application Documents** – AI-generated CVs and cover letters

```bash
# Generate tailored CV and cover letter
job app write 42 --cv cv.toml --letter letter.toml

# View generated drafts
job app view 1

# List all drafts
job app list
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
job gh issue -f 1 --repo owner/repo
job gh issue -f 1  # uses repo from config

# Recreate issue (if already posted)
job gh issue -f 1 --repo owner/repo --force
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
job gh issue -f 1 --repo myuser/job-hunt

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
job gh i -f 1 --repo x/y      # issue
job gh c -a 5                 # comment
```

## Application Documents

Generate tailored CVs and cover letters using AI, with automatic updates to your source files.

### Drafting Documents

```bash
# Draft both CV and cover letter for a job
job app write 42 --cv cv.toml --letter letter.toml

# Draft CV only
job app write 42 --no-letter

# Draft cover letter only
job app write 42 --no-cv

# Add context files for better personalization
job app write 42 --cv cv.toml -e persona.md -e experience.md

# Store in database without modifying source files
job app write 42 --cv cv.toml --no-apply
```

### Workflow

```bash
# 1. Add a job to your database
job add https://example.com/senior-engineer

# 2. Draft tailored application documents
job app write 1 --cv cv.toml --letter letter.toml
# → AI analyzes job requirements and your background
# → Generates tailored CV highlighting relevant experience
# → Generates cover letter addressing key requirements
# → Automatically updates cv.toml and letter.toml

# 3. Review generated content
job app view 1

# 4. Re-apply a draft to different files
job app apply 1 -i 1 --cv-dest tailored-cv.toml
```

### Managing Drafts

```bash
# List all drafts
job app list

# List drafts for a specific job
job app list 42

# View a specific draft
job app view 1

# Delete a specific draft
job app del 42 -i 1

# Delete all drafts for a job
job app del 42
```

### Aliases

```bash
job app w 42 --cv cv.toml     # write
job app v 1                   # view
job app l                     # list
job app a 42 -i 1             # apply
job app d 42                  # del
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

# Application document generation defaults
[job.app]
cv = "~/Documents/cv.toml"           # Default CV source
letter = "~/Documents/letter.toml"   # Default letter source
# extra = ["~/Documents/persona.md"]
# model = "gemini-2.5-flash"

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
# enabled = false  # Temporarily disable this page
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
job gh issue -f 2  # Uses xrsl/cv from config
job gh issue -f 2 --repo other/repo  # Override with CLI flag
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
job search [--company NAME] [--keyword KW] [--extra KW] [--since DAYS]
job add <URL> [--structured] [--browser] [--model MODEL]
job add --from-issue <NUM>
job list
job query <QUERY>
job view <ID|URL>
job export [ID|URL] [-o FILE] [-q QUERY]
job del <ID|URL>
```

### Fit Assessment

```bash
# Assess fit
job fit <JOB_ID> --cv <PATH> [--extra <PATH>] [--model MODEL]

# View assessments
job fit view <JOB_ID>             # List all for job
job fit view <JOB_ID> -i <NUM>    # View specific assessment

# Delete assessments
job fit del <JOB_ID>              # Delete all for job
job fit del <JOB_ID> -i <NUM>     # Delete specific assessment

# Aliases: f (fit), v (view)
job f 1 --cv cv.toml -e persona.md
job f v 1 -i 5
```

### GitHub Integration

```bash
# Create issue from job
job gh issue -f <JOB_ID> --repo <OWNER/REPO>
job gh issue -f <JOB_ID>  # uses repo from config

# Post assessment as comment
job gh comment -a <ASSESSMENT_ID> --repo <OWNER/REPO> --issue <NUM>
job gh comment -a <ASSESSMENT_ID>  # auto-detect repo/issue

# Aliases: i (issue), c (comment)
job gh i -f 1 --repo user/repo
job gh c -a 5
```

### Application Documents

```bash
# Generate tailored documents
job app write <JOB_ID> --cv <PATH> --letter <PATH>
job app write <JOB_ID> --no-letter          # CV only
job app write <JOB_ID> --no-apply           # Don't modify source files

# View and manage drafts
job app view <DRAFT_ID>
job app list [JOB_ID]
job app apply <JOB_ID> -i <DRAFT_ID>
job app del <JOB_ID> [-i <DRAFT_ID>]

# Aliases: w (write), v (view), l (list), a (apply), d (del)
job app w 1 --cv cv.toml
job app v 1
```

### Database

```bash
job db path       # Show database path
job db stats      # Show statistics
job db migrate    # Migrate schema to latest version
job db del        # Delete database
```

### Utilities

```bash
# List supported AI models
job lm                        # All models
job lm gemini                 # Filter by provider
job lm -e preview             # Exclude preview models

# Update job fields
job upt <JOB_ID> <FIELD> <VALUE>
job upt 1 title "Senior Python Developer"
job upt 1 location "Remote"

# Available fields: title, company, location, deadline, department,
# hiring_manager, job_posting_url, github_repo, github_issue_number
```

## Architecture

**Stack:** Python 3.12+ • Typer • SQLModel • Pydantic AI • Playwright • BeautifulSoup
