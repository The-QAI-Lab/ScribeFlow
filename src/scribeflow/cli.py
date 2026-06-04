"""ScribeFlow CLI entrypoint placeholders."""

import typer

app = typer.Typer(help="ScribeFlow CLI")


@app.command()
def version() -> None:
    """Print version placeholder."""
    typer.echo("ScribeFlow 0.1.0")
