import typer

# Shared CLI application instance
app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
