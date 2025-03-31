#!/usr/bin/env python3
"""Plot multi-segment rupture stoch file with slip."""

from pathlib import Path
from typing import Annotated, Optional

import numpy as np
import typer
from matplotlib import pyplot as plt

from qcore import cli
from source_modelling import stoch
from visualisation import utils

app = typer.Typer()


def plot_stoch(
    stoch_data: stoch.StochFile,
    width: float = 10,
    height: float = 10,
) -> tuple[plt.Figure, list[list[plt.Axes]] | plt.Axes]:
    """Plot multi-segment rupture with slip.

    The plot is a heatmap of the slip distribution of the stoch file.
    The heatmap is labelled with the length along the x-axis and the
    width along the y-axis (both in kilometres). The heatmap is
    coloured with a reverse hot colourmap (like the SRF segment
    plots). The text labels are coloured white for high values and
    black for low values. See the examples in the wiki.

    Parameters
    ----------
    stoch_data : StochFile
        Stoch file to plot.
    width : float, optional
        Width of plot (in cm). Default is 10.
    height : float, optional
        Height of plot (in cm). Default is 10.

    Returns
    -------
    plt.Figure
        Figure of the plot.
    list[list[plt.Axes]] | plt.Axes
        Axes of the plot. Will be a list if there are multiple segments.

    Examples
    --------
    >>> stoch_data = stoch.StochFile("tests/stochs/rupture_1.stoch")
    >>> fig, axes = plot_stoch(stoch_data, width=10, height=10)
    >>> # The above code would plot the slip distribution of the stoch file 'rupture_1.stoch'.
    >>> # The plot will have a width of 10 cm and a height of 10 cm.
    """
    cm = 1 / 2.54
    rows = int(np.sqrt(len(stoch_data.data)))
    cols = int(np.ceil(len(stoch_data.data) / rows))
    fig, axes = plt.subplots(rows, cols, figsize=(width * cm, height * cm))
    for i, (ax, plane_data, slip) in enumerate(
        zip(axes.ravel(), stoch_data.data, stoch_data.slip)
    ):
        dx = plane_data.header.dx
        dy = plane_data.header.dy
        length = dx * slip.shape[1]
        width = dy * slip.shape[0]
        description = utils.format_description(slip, compact=True, units="cm")
        ax.set_title(f"Segment {i + 1}\n{description}")

        # Plot slip array as a heatmap labelled with length along the x-axis and width along the x-axis.
        ax.set_ylim(width, 0)
        ax.imshow(
            slip[::-1],
            cmap="hot_r",
            extent=[0, length, 0, width],
        )
        ax.set_xlabel("Length (km)")
        ax.set_ylabel("Width (km)")

        for j, k in np.ndindex(slip.shape):
            # Add text labels to the heatmap, use white text for high values, and black text for low values.
            colour = "black" if slip[j, k] < np.median(slip) else "white"
            ax.text(
                k * dx + dx / 2,
                (j * dy + dy / 2),
                f"{int(slip[j,  k])}",
                ha="center",
                va="center",
                color=colour,
            )

    # empty the unused axes
    for ax in axes.ravel()[len(stoch_data.data) :]:
        ax.axis("off")

    return fig, axes


@cli.from_docstring(app)
def plot_stoch_to_file(
    stoch_ffp: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_ffp: Annotated[Path, typer.Argument(dir_okay=False)],
    width: Annotated[float, typer.Option()] = 10,
    height: Annotated[float, typer.Option()] = 10,
    dpi: Annotated[int, typer.Option()] = 300,
    title: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Plot multi-segment rupture with slip.

    Parameters
    ----------
    stoch_ffp : Path
        Path to stoch file to plot.
    output_ffp : Path
        Output plot image.
    width : float
        Width of plot (in cm).
    height : float
        Width of plot (in cm).
    dpi : int
        Plot output DPI (higher is better).
    title : Optional[str]
        Plot title to use.


    Examples
    --------
    >>> plot_stoch_to_file(
    ...     stoch_ffp="tests/stochs/rupture_1.stoch",
    ...     output_ffp="slip_plot.png",
    ...     dpi=300,
    ...     title="Rupture Slip Distribution",
    ...     latitude_pad=0.5,
    ...     longitude_pad=0.5,
    ...     annotations=True,
    ...     width=15,
    ...     show_inset=True,
    ... )
    >>> # The above code would plot the slip distribution of the stoch file 'rupture_1.stoch'
    >>> # and save it as 'slip_plot.png'.
    >>> # The plot will have a DPI of 300.
    >>> # The plot will have the title "Rupture Slip Distribution".
    >>> # The plot will have jump points marked from the realisation file 'realisation.json'.
    >>> # The plot will have a latitude and longitude padding of 0.5 degrees.
    >>> # The plot will have annotations of slip times and an inset map.
    """
    stoch_data = stoch.StochFile(stoch_ffp)
    fig, axes = plot_stoch(stoch_data, width, height)
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_ffp, dpi=dpi)


if __name__ == "__main__":
    app()
