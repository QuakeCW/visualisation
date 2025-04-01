"""Utility functions common to many plotting scripts."""

from typing import Optional

import numpy as np
import pygmt
import shapely

from qcore import coordinates


def format_description(
    arr: np.ndarray, dp: float = 0, compact: bool = False, units: Optional[str] = None
) -> str:
    """Format a statistical description of an array.

    Parameters
    ----------
    arr : np.ndarray
        Input array.
    dp : float, optional
        Decimal places to round to, by default 0.
    compact : bool, optional
        Whether to return a compact string (i.e. on one line), by default False.
    units : str, optional
        The units of the values.

    Returns
    -------
    str
        Formatted string containing min, mean, max, and standard deviation.
    """
    min = arr.min()
    mean = np.mean(arr)
    max = arr.max()
    std = np.std(arr)
    if units:
        units = " " + units
    else:
        units = ""
    min_label = f"min = {min:.{dp}f}{units}"
    mean_label = f"μ = {mean:.{dp}f}{units}"
    max_label = f"max = {max:.{dp}f}{units}"
    std_label = f"σ = {std:.{dp}f}{units}"
    if compact:
        return f"{min_label} / {mean_label} / {std_label} / {max_label}"
    return f"{min_label}\n{mean_label} ({std_label})\n{max_label}"


def nztm_to_wgs_wraparound(coords: np.ndarray) -> np.ndarray:
    """Convert NZTM coordinates to WGS84, wrapping around the international date line for PyGMT.


    Parameters
    ----------
    coords : np.ndarray
        NZTM coordinates to convert.

    Returns
    -------
    np.ndarray
        WGS84 coordinates, wrapped around the international date line.

    Examples
    --------
    >>> import numpy as np
    >>> coords = np.array([5238700.07489416, 1518491.35216903])
    >>> nztm_to_wgs_wraparound(coords)
    array([172.0, -43.0])
    >>> coords = np.array(coordinates.wgs_depth_to_nztm(np.array([-43, 181])))
    >>> nztm_to_wgs_wraparound(coords)
    array([181.0, -43.0])
    """
    coords = coordinates.nztm_to_wgs_depth(coords)[:, ::-1]
    coords[coords[:, 0] < 0, 0] += 360
    return coords


def polygon_nztm_to_pygmt(polygon: shapely.Polygon) -> shapely.Polygon:
    """Convert a polygon from NZTM to WGS84, wrapping around the international date line for PyGMT.

    Parameters
    ----------
    polygon : shapely.Polygon
        Polygon to convert.

    Returns
    -------
    shapely.Polygon
        Converted polygon.

    Examples
    --------
    >>> import shapely
    >>> p = shapely.Point(5238700.07489416, 1518491.35216903)
    >>> polygon_nztm_to_pygmt(p)
    <POINT (172 -43)>
    >>> q = shapely.Point(*coordinates.wgs_depth_to_nztm(np.array([-43, 181])))
    >>> polygon_nztm_to_pygmt(q)
    <POINT (181 -43)>
    >>> # Note that the coordinates would be negative if coordinates
    >>> # were not wrapped around the international date line.
    """
    return shapely.transform(
        polygon,
        lambda x: nztm_to_wgs_wraparound(x),
    )


def plot_polygon(
    fig: pygmt.Figure,
    polygon: shapely.LineString
    | shapely.MultiLineString
    | shapely.Polygon
    | shapely.MultiPolygon,
    **kwargs,
) -> None:
    """Plot a polygon on a pygmt figure.

    Parameters
    ----------
    fig : pygmt.Figure
        Figure to plot on.
    polygon : polygon, linestring, or collection of polygons or linestrings
        Polygon to plot.
    **kwargs
        Additional arguments to pass to `pygmt.Figure.plot`.

    Examples
    --------
    >>> import pygmt
    >>> import shapely.geometry
    >>> fig = pygmt.Figure()
    >>> polygon = shapely.geometry.Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    >>> plot_polygon(fig, polygon, pen="1p,blue,-")
    """

    if isinstance(polygon, shapely.MultiPolygon | shapely.MultiLineString):
        for part in polygon.geoms:
            plot_polygon(fig, part, **kwargs)
    elif isinstance(polygon, shapely.LineString):
        coords = np.array(polygon.coords)
        fig.plot(
            x=coords[:, 0],
            y=coords[:, 1],
            **kwargs,
        )
    else:
        polygon_coords = np.array(polygon.exterior.coords)
        fig.plot(
            x=polygon_coords[:, 0],
            y=polygon_coords[:, 1],
            **kwargs,
        )
