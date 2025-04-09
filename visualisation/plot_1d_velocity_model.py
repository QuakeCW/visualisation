"""Plot the 1D velocity model from a realisation."""

from enum import StrEnum, auto
from pathlib import Path
from typing import Annotated

import typer
from matplotlib import pyplot as plt

from qcore import cli
from workflow.realisations import VelocityModel1D

app = typer.Typer()


class Panel(StrEnum):
    """The panels to plot."""

    VP = auto()
    VS = auto()
    DENSITY = auto()
    QP = auto()
    QS = auto()
    MU = auto()


def plot_1d_velocity_model(
    velocity_model: VelocityModel1D,
    panels: list[Panel],
    subplot_width: float = 10,
    subplot_height: float = 10,
) -> tuple[plt.Figure, list[plt.Axes]]:
    """Plot a 1D-velocity model.

    Parameters
    ----------
    velocity_model : VelocityModel1D
        The velocity model read from a realisation.
    panels : list[Panel]
        The subplot panels to plot. See `Panel` for options.
    subplot_width : float
        The width of the individual subplots.
    subplot_height : float
        The height of the individual subplots.


    Returns
    -------
    plt.Figure
        The figure object.
    list[plt.Axes]
        The axes objects.
    """
    cm = 1 / 2.54
    fig, axes = plt.subplots(
        len(panels),
        1,
        sharex=True,
        figsize=(subplot_width * cm, subplot_height * cm),
    )
    if isinstance(axes, plt.Axes):
        axes = [axes]
    model_df = velocity_model.model
    depth = model_df["thickness"].cumsum() - model_df["thickness"]
    for panel, ax in zip(panels, axes):
        match panel:
            case Panel.VP:
                y = model_df["Vp"]
                ylabel = "Vp (km/s)"
                title = "P-wave velocity"
            case Panel.VS:
                y = model_df["Vs"]
                ylabel = "Vs (km/s)"
                title = "S-wave velocity"
            case Panel.DENSITY:
                y = model_df["rho"]
                ylabel = "Density (g/cm^3)"
                title = "Density"
            case Panel.QP:
                y = model_df["Qp"]
                ylabel = "Qp"
                title = "P-wave quality factor"
            case Panel.QS:
                y = model_df["Qs"]
                ylabel = "Qs"
                title = "S-wave quality factor"
            case Panel.MU:
                y = model_df["Vs"] ** 2 * model_df["rho"]
                ylabel = "Shear modulus (N/km^2)"
                title = "Shear modulus"

        ax.step(depth, y)
        ax.set_ylabel(ylabel)
        cum_thickness: float = 0.0
        y_values_marked = []

        for thickness, depth_val, y_val in zip(model_df["thickness"], depth, y):
            cum_thickness += thickness
            if cum_thickness < 0.5:
                continue
            cum_thickness = 0
            y_values_marked.append(y_val)
            ax.axhline(
                y_val,
                color="gray",
                linestyle="--",
                alpha=0.7,
            )
        ax.set_yticks(y_values_marked)
        ax.set_title(title)

    ax.set_xlabel("Depth (km)")

    return (fig, axes)


@cli.from_docstring(app)
def plot_1d_velocity_model_to_file(
    velocity_model_file: Annotated[
        Path, typer.Argument(exists=True, readable=True, dir_okay=False)
    ],
    output_file: Annotated[Path, typer.Argument(dir_okay=False, writable=True)],
    panels: Annotated[list[Panel], typer.Option("--panel", case_sensitive=False)] = [
        Panel.MU
    ],
    subplot_width: Annotated[float, typer.Option(min=0)] = 10,
    subplot_height: Annotated[float, typer.Option(min=0)] = 10,
    dpi: Annotated[int, typer.Option(min=0)] = 300,
    title: Annotated[str | None, typer.Option()] = None,
):
    """Plot the 1D velocity model from a realisation.

    Parameters
    ----------
    velocity_model_file : Path
        The path to the velocity model file.
    output_file : Path
        The path to save the plot.
    panels : list[Panel]
        The panels to plot.
    subplot_width : float
        The width of the individual subplots.
    subplot_height : float
        The height of the individual subplots.
    dpi : int
        The resolution of the plot (higher is better).
    title : str, optional
        The title of the plot.
    """
    velocity_model = VelocityModel1D.read_from_realisation(velocity_model_file)
    fig, axes = plot_1d_velocity_model(
        velocity_model, panels, subplot_width, subplot_height
    )
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_file, dpi=dpi)
