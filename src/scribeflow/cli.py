"""ScribeFlow CLI entrypoint placeholders."""

import typer

from scribeflow import __version__

app = typer.Typer(help="ScribeFlow CLI")


@app.command()
def version() -> None:
    """Print version placeholder."""
    typer.echo(f"ScribeFlow {__version__}")
