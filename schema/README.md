# Configuration Schema

This directory contains the JSON Schema for `job-search.toml`.

## Usage

Add this to the top of your `job-search.toml`:

```toml
#:schema https://raw.githubusercontent.com/xrsl/job/v0.1.0/schema/schema.json
```

## Schema Versions

Each release has a versioned schema:

- `v0.1.0`: Initial release schema
- `v0.2.0`: (future) Updated schema

Always pin to a specific version tag for stability.

## Schema Development

The schema is defined in CUE and compiled to JSON Schema:

```bash
# Generate schema.json from schema.cue
just schema
```

## Validation

Validate your config with [tombi](https://github.com/tombi-toml/tombi):

```bash
tombi lint job-search.toml
tombi format job-search.toml
```

## IDE Support

With the schema URL, editors provide:

- **Autocomplete** for field names
- **Validation** for required fields
- **Tooltips** with field descriptions

Supported editors:

- VS Code (with Even Better TOML extension)
- IntelliJ IDEA
- Tombi CLI

## Schema URL Format

```
https://raw.githubusercontent.com/xrsl/job/refs/tags/{VERSION}/schema/schema.json
```

Replace `{VERSION}` with the release tag (e.g., `v0.1.0`).
