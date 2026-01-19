# Job CLI

A command-line tool for managing job postings. Scrapes job ads from URLs and uses AI to extract structured information.

## Installation

```bash
# Using uv
uv sync
uv run playwright install  # First-time browser setup

# Or use justfile
just setup
```

## Usage

### Adding & Managing Jobs

```bash
# Add a job posting
job add https://example.com/careers/123

# List all jobs
job list

# Show a specific job
job show https://example.com/careers/123

# Find jobs in local database
job find "python"

# Update an existing job
job update https://example.com/careers/123

# Delete a job
job rm https://example.com/careers/123

# Export jobs
job export --format json -o jobs.json
job export --format csv -o jobs.csv

# Show database info
job info

# Verbose mode (for debugging)
job --verbose add https://example.com/careers/123
```

### Searching Career Pages

The `search` command lets you monitor multiple career pages for job keywords:

```bash
# Search all configured career pages
job search

# Search with verbose output (shows match context)
job search --verbose

# Search a specific company
job search --company "Novo Nordisk"

# Add extra keywords to search
job search --keyword "rust" --keyword "golang"

# Use a custom config file
job search --config ~/my-config.toml
```

## Configuration

### Environment Variables

| Variable            | Description               | Default                      |
| ------------------- | ------------------------- | ---------------------------- |
| `JOB_MODEL`         | AI model for extraction   | `gemini-2.5-flash`           |
| `JOB_DB_PATH`       | Custom database path      | `~/.local/share/job/jobs.db` |
| `JOB_SEARCH_CONFIG` | Path to job-search.toml   | `./job-search.toml`          |
| `GEMINI_API_KEY`    | API key for Gemini models | (required)                   |

### Example `.env`

```bash
GEMINI_API_KEY=your-api-key-here
JOB_MODEL=gemini-2.5-flash
# JOB_DB_PATH=/custom/path/jobs.db  # Optional
```

### Job Search Configuration (`job-search.toml`)

Configure career pages to monitor and keywords to search for:

```toml
# Keywords to search for across all pages
[job.search]
keywords = ["python", "backend", "engineer", "senior", "machine learning"]

# Career pages to scan
[[job.search.in]]
company = "Spotify"
link = "https://www.lifeatspotify.com/jobs"

[[job.search.in]]
company = "Stripe"
link = "https://stripe.com/jobs/search"

# Page with custom keywords (overrides job.search.keywords)
[[job.search.in]]
company = "Linear"
link = "https://linear.app/careers"
keywords = ["frontend", "react", "typescript"]

# Disabled page (skipped during search)
[[job.search.in]]
company = "Paused Corp"
link = "https://example.com/careers"
enabled = false
```

Config file locations (checked in order):
1. `JOB_SEARCH_CONFIG` environment variable
2. `./job-search.toml` (current directory)
3. `~/.config/job/job-search.toml`
4. `~/.job-search.toml`

## Commands

| Command  | Description                                       |
| -------- | ------------------------------------------------- |
| `add`    | Add a new job posting (scrapes and extracts info) |
| `update` | Re-fetch and update an existing job               |
| `list`   | List all stored job ads                           |
| `show`   | Show details of a specific job                    |
| `find`   | Find jobs in local database by keyword            |
| `rm`     | Delete a job by URL                               |
| `export` | Export jobs to JSON or CSV                        |
| `info`   | Show database location and stats                  |
| `search` | Search career pages for job keywords              |

## Development

```bash
# Format code
just fmt

# Lint
just lint

# Run the CLI
just run add https://example.com/job
```

## Database

By default, the database is stored at `~/.local/share/job/jobs.db` (XDG-compliant).

You can override this with the `JOB_DB_PATH` environment variable.
