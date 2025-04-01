from pathlib import Path
from typing import Annotated

import numpy as np
import pandas as pd
import pygmt
import shapely
import typer
from velocity_modelling.bounding_box import BoundingBox

from pygmt_helper import plotting
from qcore import cli, coordinates
from qcore.uncertainties import mag_scaling
from visualisation import utils
from workflow.realisations import (
    DomainParameters,
    RupturePropagationConfig,
    SourceConfig,
    VelocityModelParameters,
)
from workflow.scripts import generate_velocity_model_parameters

app = typer.Typer()


def plot_stations(fig: pygmt.Figure, domain: BoundingBox, stations_path: Path) -> None:
    stations = pd.read_csv(
        stations_path, delimiter=r"\s+", comment="#", names=["lon", "lat", "name"]
    )
    stations_in_domain = np.count_nonzero(
        domain.contains(stations[["lat", "lon"]].to_numpy())
    )
    fig.plot(
        x=stations["lon"],
        y=stations["lat"],
        style="t0.1c",
        fill="red",
        pen="black",
        label=f"Stations ({stations_in_domain})",
    )


def bounding_region_for(
    polygon: shapely.Polygon | list[shapely.Polygon],
    latitude_pad: float,
    longitude_pad: float,
) -> utils.Region:
    if isinstance(polygon, list):
        polygon = shapely.union_all(polygon)

    bounds = shapely.bounds(utils.polygon_nztm_to_pygmt(polygon))
    return (
        bounds[0] - longitude_pad,
        bounds[2] + longitude_pad,
        bounds[1] - latitude_pad,
        bounds[3] + latitude_pad,
    )


@cli.from_docstring(app)
def plot_domain_to_file(
    realisation_ffp: Annotated[
        Path,
        typer.Argument(
            help="Path to realisation file.", dir_okay=False, exists=True, readable=True
        ),
    ],
    output_ffp: Annotated[
        Path,
        typer.Argument(
            help="Path to output image file path", dir_okay=False, writable=True
        ),
    ],
    latitude_pad: Annotated[
        float, typer.Option(help="Latitude padding in degrees.", min=0)
    ] = 0,
    longitude_pad: Annotated[
        float,
        typer.Option(help="Longitude padding in degrees.", min=0),
    ] = 0,
    title: Annotated[
        str | None,
        typer.Option(
            help="Title of the plot.",
        ),
    ] = None,
    subtitle: Annotated[
        str | None,
        typer.Option(
            help="Subtitle of the plot.",
        ),
    ] = None,
    width: Annotated[
        float,
        typer.Option(
            help="Width of the plot in cm.",
            min=0,
        ),
    ] = 10,
    dpi: Annotated[
        float,
        typer.Option(
            help="DPI of the plot (higher is better quality).",
            min=0,
        ),
    ] = 300,
    show_geonet_stations: Annotated[
        bool,
        typer.Option(
            help="Show GeoNet stations on the plot.",
            show_default=False,
        ),
    ] = False,
    show_geometry: Annotated[
        bool,
        typer.Option(
            help="Show source geometry on the plot.",
        ),
    ] = True,
    show_pgv_targets: Annotated[
        bool,
        typer.Option(
            help="Show PGV targets on the plot.",
        ),
    ] = False,
    pgv_targets: Annotated[
        list[float] | None,
        typer.Option(
            help="PGV targets to plot. If None, use PGV targets from the realisation.",
        ),
    ] = None,
    stations: Annotated[
        Path | None,
        typer.Option(
            help="Path to stations file to plot.",
            exists=True,
            readable=True,
        ),
    ] = None,
) -> None:
    """Plot the domain of a realisation to a file.

    Parameters
    ----------
    realisation_ffp : Path
        Path to the realisation file to plot.
    output_ffp : Path
        Path to output image file path.
    latitude_pad : float
        Latitude padding in degrees.
    longitude_pad : float
        Longitude padding in degrees.
    title : str, optional
        Title of the plot.
    subtitle : str, optional
        Subtitle of the plot.
    width : float
        Width of the plot in cm.
    dpi : float
        DPI of the plot (higher is better quality).
    show_geonet_stations : bool
        Show GeoNet stations on the plot.
    show_geometry : bool
        Show source geometry on the plot.
    show_pgv_targets : bool
        Show PGV targets on the plot.
    pgv_targets : list[float], optional
        PGV targets to plot. If None, use PGV targets from the realisation.
    stations : Path, optional
        Path to list of stations to plot.
    """

    rupture_propagation = RupturePropagationConfig.read_from_realisation(
        realisation_ffp
    )
    domain = DomainParameters.read_from_realisation(realisation_ffp).domain

    velocity_model_parameters = VelocityModelParameters.read_from_realisation(
        realisation_ffp
    )

    source_config = SourceConfig.read_from_realisation(realisation_ffp)

    source_geometry = shapely.union_all(
        [source.geometry for source in source_config.source_geometries.values()]
    )
    rrup_bounding_polygons: list[shapely.Polygon] = []
    region = None
    if show_pgv_targets:
        fault_pgv_targets = pgv_targets or [
            generate_velocity_model_parameters.pgv_target(
                rupture_propagation, velocity_model_parameters
            )
        ]

        for pgv_targets in fault_pgv_targets:
            rrup_bounding_polygons.append(
                shapely.union_all(
                    [
                        generate_velocity_model_parameters.find_rrup_bounding_polygon(
                            *args, pgv_target=pgv_targets
                        )
                        for args in generate_velocity_model_parameters.dict_zip(
                            source_config.source_geometries,
                            rupture_propagation.magnitudes,
                            rupture_propagation.rakes,
                        ).values()
                    ]
                )
            )

    region = bounding_region_for(
        [domain.polygon] + rrup_bounding_polygons,
        latitude_pad=latitude_pad,
        longitude_pad=longitude_pad,
    )

    fig = plotting.gen_region_fig(
        title,
        region,
        projection=f"M{width}c",
        subtitle=subtitle,
    )

    utils.plot_polygon(
        fig, utils.polygon_nztm_to_pygmt(domain.polygon), pen="1p,blue,-"
    )

    if show_geometry:
        utils.plot_polygon(
            fig, utils.polygon_nztm_to_pygmt(source_geometry), pen="0.3p,black"
        )

    if stations:
        plot_stations(fig, domain, stations)

    if show_pgv_targets:
        for pgv_target, rrup_bounding_polygon in zip(
            fault_pgv_targets, rrup_bounding_polygons
        ):
            utils.plot_polygon(
                fig,
                utils.polygon_nztm_to_pygmt(rrup_bounding_polygon),
                pen="0.3p,black,-",
            )
            utils.label_polygon(
                fig,
                region,
                utils.polygon_nztm_to_pygmt(rrup_bounding_polygon),
                f"{pgv_target} cm/s",
                fill="white",
                pen="0.3p,black",
            )

    # Plot the legend overtop the other elements.
    if stations:
        fig.legend(position="jTR+o0.2c", box="+gwhite+p1p")

    fig.savefig(output_ffp, dpi=dpi)


if __name__ == "__main__":
    app()
