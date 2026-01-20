# Schema Configuration

This directory contains the JSON Schema for `job-search.toml`.

## Schema Usage

Add this to the top of your `job-search.toml`:

```toml
#:schema https://raw.githubusercontent.com/xrsl/job/v0.2.0/schema/schema.json
```

## Schema-based Validation

Validate your config with [tombi](https://github.com/tombi-toml/tombi) cli:

```bash
tombi lint job-search.toml
tombi format job-search.toml
```

## Schema Development

The schema is defined in CUE and compiled to JSON Schema:

```bash
# Generate schema.json from schema.cue
just schema
```

## IDE Support

With the schema URL, editors provide:

- **Autocomplete** for field names
- **Validation** for required fields
- **Tooltips** with field descriptions

Supported editors:

- VS Code or any other VSC compatible editor (with [Tombi](https://github.com/tombi-toml/tombi) extension installed)
