# Job CLI

A command-line tool for managing job postings. Scrapes job ads from URLs and uses AI to extract structured information.

## Installation

Install directly from GitHub using `uv`:

```bash
# Install from releases
uv tool install github:xrsl/job # the latest
uv tool install github:xrsl/job@v0.1.0

```

## Quick Start

### Job Search (Discovery)

Monitor multiple career pages for keywords you care about.

```bash
# Search all configured pages with default keywords
job search
```

**Filtering & Customizing:**

```bash
# Filter by company (fuzzy match)
job search --company spotify

# Override keywords (replaces defaults)
job search --company spotify --keyword python

# Append extra keywords to defaults
job search --extra "rust" --extra "go"
```

**Real-time Output:**
The search runs in parallel (where applicable) and shows:

- A spinner while fetching pages.
- Real-time found positions.
- Clickable links to the career pages directly in your terminal.

### Job Management (Tracking)

Keep track of interesting positions you find.

```bash
# Add a job (scrapes and extracts info via AI)
job add https://example.com/careers/123

# List your saved jobs
job list

# Find jobs in your database
job find "python"

# Show details
job show https://example.com/careers/123

# Export data
job export --format json -o my_jobs.json
```

## Configuration (`job-search.toml`)

Configure career pages and default keywords in `job-search.toml`:

```toml
# Default keywords for all pages
[job.search]
keywords = ["python", "backend", "engineer", "senior"]

# Add a career page
[[job.search.in]]
company = "Spotify"
link = "https://www.lifeatspotify.com/jobs"

# Page with custom keywords (overrides defaults)
[[job.search.in]]
company = "Linear"
link = "https://linear.app/careers"
keywords = ["frontend", "react", "typescript"]

# Disabled page
[[job.search.in]]
company = "Archived Co"
link = "..."
enabled = false
```

## Environment Variables

| Variable            | Description               | Default                      |
| ------------------- | ------------------------- | ---------------------------- |
| `JOB_MODEL`         | AI model for extraction   | `gemini-2.5-flash`           |
| `JOB_DB_PATH`       | Custom database path      | `~/.local/share/job/jobs.db` |
| `JOB_SEARCH_CONFIG` | Path to job-search.toml   | `./job-search.toml`          |
| `GEMINI_API_KEY`    | API key for Gemini models | (required)                   |
