"""Create simulation video of surface ground motion levels."""

import shutil
from pathlib import Path
from typing import Annotated

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib
import shapely

matplotlib.use("Agg")

import matplotlib.animation as animation
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import typer
from tqdm import tqdm

from qcore import cli, coordinates
from qcore.xyts import XYTSFile
from visualisation import utils
from workflow.realisations import SourceConfig

app = typer.Typer()

NZTM_CRS = ccrs.epsg(2193)
LATLON_CRS = ccrs.PlateCarree()


def apply_cmap_with_alpha(x: np.ndarray, vmin: float, vmax: float, cmap: str = "hot"):
    """Map the input array x into the 'hot' colormap with linear scaling on alpha.

    Parameters
    ----------
    x : np.ndarray
        Input array to be colour-mapped.
    vmin : float
        Minimum value for normalisation.
    vmax : float
        Maximum value for normalisation.
    cmap: str, optional
        The colour-map to apply to the input array. Default is hot.

    Returns
    -------
    np.ndarray
        RGBA values of the array x mapped using the `cmap` colour-map and linear alpha scaling.
    """
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    cmap = plt.get_cmap("hot")
    rgb = cmap(norm(x))[..., :3]

    alpha = norm(x)
    rgba = np.concatenate([rgb, alpha[..., np.newaxis]], axis=-1)

    return np.clip(rgba, 0, 1)


def plot_towns(ax: plt.Axes) -> None:
    """Plot towns on the map.

    Parameters
    ----------
    ax : plt.Axes
        The axes to plot the towns on.
    """
    towns = {
        "Blenheim": (173.9569444, -41.5138888),
        "Christchurch": (172.6347222, -43.5313888),
        "Dunedin": (170.3794444, -45.8644444),
        "Greymouth": (171.2063889, -42.4502777),
        "Haast": (169.0405556, -43.8808333),
        "Kaikoura": (173.6802778, -42.4038888),
        "Masterton": (175.658333, -40.952778),
        "Napier": (176.916667, -39.483333),
        "New Plymouth": (174.083333, -39.066667),
        "Nelson": (173.2838889, -41.2761111),
        "Palmerston North": (175.611667, -40.355000),
        "Queenstown": (168.6680556, -45.0300000),
        "Rakaia": (172.0230556, -43.75611111),
        "Rotorua": (176.251389, -38.137778),
        "Taupo": (176.069400, -38.6875),
        "Tekapo": (170.4794444, -44.0069444),
        "Timaru": (171.2430556, -44.3958333),
        "Wellington": (174.777222, -41.288889),
        "Westport": (171.5997222, -41.7575000),
    }
    for town_name, (lon, lat) in towns.items():
        ax.plot(
            lon,
            lat,
            "o",
            markersize=4,
            color="white",
            markeredgecolor="black",
            transform=LATLON_CRS,
            zorder=4,
        )

        ax.text(
            lon,
            lat,
            " " + town_name,
            fontsize=8,
            color="black",
            ha="left",
            va="center",
            transform=LATLON_CRS,
            zorder=5,
        )


def plot_cartographic_features(ax: plt.Axes, scale: str) -> None:
    """Add cartographic features to the map.

    Parameters
    ----------
    ax : plt.Axes
        The axes to plot the features on.
    scale : str
        The scale for the cartographic features.
    """
    ax.add_feature(cfeature.LAND.with_scale(scale), facecolor="#dcdcdc", zorder=1)

    ax.add_feature(cfeature.OCEAN.with_scale(scale), facecolor="#b0c4de", zorder=0)
    ax.add_feature(
        cfeature.COASTLINE.with_scale(scale),
        linewidth=0.5,
        edgecolor="black",
        zorder=2,
    )
    ax.add_feature(
        cfeature.BORDERS.with_scale(scale),
        linestyle=":",
        edgecolor="grey",
        zorder=1,
    )
    ax.add_feature(
        cfeature.LAKES.with_scale(scale),
        alpha=0.5,
        facecolor="#b0c4de",
        edgecolor="black",
        linewidth=0.2,
        zorder=1,
    )

    gl = ax.gridlines(
        draw_labels=True, linewidth=0.5, alpha=0.3, color="gray", linestyle="--"
    )
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8, "rotation": 45}
    gl.ylabel_style = {"size": 8}


def xyts_nztm_corners(xyts_file: XYTSFile) -> np.ndarray:
    """Get the corners of the XYTS file in NZTM coordinates.

    Parameters
    ----------
    xyts_file : XYTSFile
            The XYTS file to get the corners from.

    Returns
    -------
    np.ndarray
            The corners of the XYTS file in NZTM coordinates.
    """
    corners_geo = np.array(xyts_file.corners())
    return coordinates.wgs_depth_to_nztm(corners_geo[:, ::-1])[:, ::-1]


def map_extents(
    nztm_corners: np.ndarray, padding: float
) -> tuple[float, float, float, float]:
    """Compute map extents from XYTS file.

    Parameters
    ----------
    nztm_corners : np.ndarray
        The corners of the XYTS domain.
    padding : float
        A padding around the domain (in metres).

    Returns
    -------
    tuple[float, float, float, float]
        The map extents for the figure (x_min, x_max, y_min, y_max).
    """
    x_min, x_max = nztm_corners[:, 0].min(), nztm_corners[:, 0].max()
    y_min, y_max = nztm_corners[:, 1].min(), nztm_corners[:, 1].max()

    padding_m = padding * 1000

    map_extent_nztm = [
        x_min - padding_m,
        x_max + padding_m,
        y_min - padding_m,
        y_max + padding_m,
    ]

    return map_extent_nztm


def xyts_waveform_coordinates(xyts_file: XYTSFile) -> np.ndarray:
    """Compute gridpoint coordinates for XYTS waveform.

    Parameters
    ----------
    xyts_file : XYTSFile
        The xyts file containing gridded data.


    Returns
    -------
    np.ndarray
        A numpy array of shape (2 x ny x nx) containing the x and y
        coordinates of gridpoints in the NZTM coordinate system.
    """
    corners_geo = np.array(xyts_file.corners())
    nztm_corners = coordinates.wgs_depth_to_nztm(corners_geo[:, ::-1])

    norm_xi, norm_eta = np.meshgrid(
        np.linspace(0, 1, xyts_file.nx), np.linspace(0, 1, xyts_file.ny)
    )
    origin = nztm_corners[0]  # Bottom-left corner (x0, y0) in NZTM
    vec_x = nztm_corners[1] - origin  # Vector along xi axis (bottom edge) in NZTM
    vec_y = nztm_corners[3] - origin  # Vector along eta axis (left edge) in NZTM

    coords_nztm = (
        origin[:, np.newaxis, np.newaxis]
        + vec_x[:, np.newaxis, np.newaxis] * norm_xi[np.newaxis, :, :]
        + vec_y[:, np.newaxis, np.newaxis] * norm_eta[np.newaxis, :, :]
    )
    return coords_nztm[::-1, :, :]  # Reverse order to (x, y) for NZTM


@cli.from_docstring(app)
def animate_low_frequency_mpl_nztm(
    realisation_ffp: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    xyts_ffp: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output_mp4: Annotated[Path, typer.Argument(writable=True, dir_okay=False)],
    max_motion: Annotated[float, typer.Option()] = 10.0,
    padding: Annotated[float, typer.Option()] = 5.0,
    cmap: Annotated[str, typer.Option()] = "hot",
    scale: Annotated[str, typer.Option()] = "10m",
    shading: Annotated[str, typer.Option()] = "gouraud",
    frame_count: Annotated[int | None, typer.Option()] = None,
    width: Annotated[float, typer.Option()] = 30.0,
    height: Annotated[float, typer.Option()] = 30.0,
    dpi: Annotated[float, typer.Option()] = 150.0,
    fps: Annotated[float, typer.Option()] = 15.0,
    title: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Render low-frequency output as a 2D video of ground motions.

    Parameters
    ----------
    realisation_ffp : Path
        The input realisation file.
    xyts_ffp : Path
        The input xyts file containing the simulation data.
    output_mp4 : Path
        The output file path for the generated animation.
    max_motion : float, optional
        The maximum ground motion value for color scaling, by default 10.0.
    padding : float, optional
        The padding in km for the map extent, by default 5.0.
    cmap : str, optional
        The colormap to use for the animation, by default "hot".
    scale : str, optional
        The scale for cartopy features, by default "10m".
    shading : str, optional
        The shading method for `plt.pcolormesh`, by default "gouraud".
    frame_count : int | None, optional
        The number of frames to display in the animation, by default None (uses all frames).
    width : float, optional
        The width of the figure in cm, by default 30.
    height : float, optional
        The height of the figure in cm, by default 30.
    dpi : float, optional
        The DPI for the figure, by default 150.0.
    fps : float, optional
        The frames per second for the animation, by default 15.0.
    title : str | None, optional
        The title for the animation, by default None (no title).
    """

    if not shutil.which("ffmpeg"):
        print(
            "You must have ffmpeg installed. See https://ffmpeg.org/download.html.",
        )
        raise typer.Exit(code=1)

    cm = 1 / 2.54
    source_config = SourceConfig.read_from_realisation(realisation_ffp)
    xyts_file = XYTSFile(xyts_ffp)

    ground_motion_magnitude = np.linalg.norm(xyts_file.data, axis=1)

    fig = plt.figure(figsize=(width * cm, height * cm))
    ax = fig.add_subplot(1, 1, 1, projection=NZTM_CRS)
    nztm_corners = xyts_nztm_corners(xyts_file)
    map_extent_nztm = map_extents(nztm_corners, padding)
    ax.set_extent(map_extent_nztm, crs=NZTM_CRS)

    xr, yr = xyts_waveform_coordinates(xyts_file)
    initial_data = ground_motion_magnitude[0, :, :]
    pcm = ax.pcolormesh(
        xr,
        yr,
        apply_cmap_with_alpha(initial_data, 0, max_motion),
        cmap=cmap,
        vmin=0,
        vmax=max_motion,
        shading=shading,
        zorder=3,
        rasterized=True,
    )
    cbar = fig.colorbar(
        pcm, ax=ax, orientation="vertical", pad=0.02, aspect=30, shrink=0.8
    )
    cbar.set_label("Ground Motion (cm/s)")

    time_text = ax.text(
        0.98,
        0.02,
        "",
        transform=ax.transAxes,
        fontsize=12,
        color="black",
        fontweight="bold",
        ha="right",
        va="bottom",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )

    if title:
        fig.suptitle(title, fontsize=16)

    plt.tight_layout()

    plot_cartographic_features(ax, scale)
    plot_towns(ax)

    ax.add_geometries(
        [shapely.Polygon(nztm_corners)],
        facecolor="none",
        edgecolor="black",
        linestyle="--",
        zorder=1,
        crs=NZTM_CRS,
    )

    ax.add_geometries(
        [
            utils.polygon_nztm_to_pygmt(fault.geometry)
            for fault in source_config.source_geometries.values()
        ],
        facecolor="red",
        edgecolor="black",
        zorder=2,
        crs=LATLON_CRS,
    )

    def update(frame_index: int):  # numpydoc ignore=GL08
        current_data = ground_motion_magnitude[frame_index, :, :]
        pcm.set_array(
            apply_cmap_with_alpha(current_data, 0, max_motion),
        )

        current_time = frame_index * xyts_file.dt
        time_text.set_text(f"Time: {current_time:.2f} s")

        return pcm, time_text

    frame_count = frame_count or xyts_file.nt
    anim = animation.FuncAnimation(
        fig, update, frames=frame_count, interval=1000 / fps, blit=True
    )

    pbar = tqdm(total=frame_count, unit="frame", desc="Rendering")

    def progress_callback(
        current_frame: int, total_frames: int
    ):  # numpydoc ignore=GL08
        pbar.update(1)

    anim.save(
        output_mp4,
        writer="ffmpeg",
        dpi=dpi,
        progress_callback=progress_callback,
    )

    pbar.close()
    plt.close(fig)
