# this file makes it possible to run the app with `python -m job`
# uv run python -m job --help
# https://typer.tiangolo.com/tutorial/package/#support-python-m-optional
from .main import app

app(prog_name="job")
