"""Command-line interface."""

import click


@click.command()
@click.version_option()
def main() -> None:
    """TemperatureAnalysis."""


if __name__ == "__main__":
    main(prog_name="temperatureanalysis")  # pragma: no cover
