import typer

app = typer.Typer()


@app.callback()
def callback():
    """
    Awesome Portal Gun
    """


@app.command()
def provision():
    """
    Shoot the portal gun
    """
    typer.echo("Shooting portal gun")


@app.command()
def job():
    """
    Load the portal gun
    """
    typer.echo("Loading portal gun")


if __name__ == "__main__":
    app()
