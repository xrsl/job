#!/usr/bin/env python3
import sys
from collections import defaultdict
from typing import get_args

try:
    # Attempt to import KnownModelName from pydantic_ai.models
    # It might be in pydantic_ai or pydantic_ai.models depending on version,
    # but docs and my test confirm pydantic_ai.models
    from pydantic_ai.models import KnownModelName
except ImportError:
    print("Error: Could not import pydantic_ai.models.KnownModelName")
    print("Ensure pydantic-ai is installed.")
    sys.exit(1)


def main():
    # KnownModelName is a TypeAliasType (in recent versions), so we access __value__ to get the Literal
    try:
        # Check if it has __value__ (TypeAliasType)
        if hasattr(KnownModelName, "__value__"):
            models = get_args(KnownModelName.__value__)
        else:
            # Fallback if it's a simple Literal (older python/typing versions maybe?)
            models = get_args(KnownModelName)
    except Exception as e:
        print(f"Error extracting models from KnownModelName: {e}")
        sys.exit(1)

    if not models:
        print("No models found in KnownModelName.")
        return

    # Group by provider (prefix before colon)
    by_provider = defaultdict(list)
    for m in models:
        if ":" in m:
            provider, name = m.split(":", 1)
            by_provider[provider].append(m)
        else:
            by_provider["other"].append(m)

    print(f"Found {len(models)} known models in pydantic_ai.\n")

    filter_str = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    for provider in sorted(by_provider.keys()):
        # If filtering, check if provider matches
        if filter_str and filter_str not in provider.lower():
            # If provider doesn't match, check if any model within it matches?
            # For simplicity, let's keep the user request "ls-m openai" implying provider filter mostly.
            # But let's be robust: if filter matches provider OR any model in it.
            matching_models = [
                m for m in by_provider[provider] if filter_str in m.lower()
            ]
            if not matching_models and filter_str not in provider.lower():
                continue
        else:
            matching_models = by_provider[provider]

        # Double check we have models to show
        if not matching_models:
            matching_models = [
                m for m in by_provider[provider] if filter_str in m.lower()
            ]
            if not matching_models:
                continue

        print(f"--- {provider.upper()} ---")
        for m in sorted(matching_models):
            print(f"  {m}")
        print()

    print("Usage example:")
    print("  job a https://example.com/job -s -m openai:gpt-4o")
    print("  job a https://example.com/job -s -m anthropic:claude-3-5-sonnet-latest")


if __name__ == "__main__":
    main()
