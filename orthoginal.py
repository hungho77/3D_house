import glob
import os
import concurrent.futures
from typing import Optional, Tuple

# PythonOCC imports
from OCC.Extend.DataExchange import read_step_file
from OCC.Extend.TopologyUtils import discretize_edge, get_sorted_hlr_edges
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Pnt2d
from OCC.Core.Bnd import Bnd_Box2d
from OCC.Core.TopoDS import TopoDS_Edge, TopoDS_Shape

try:
    import svgwrite
    HAVE_SVGWRITE = True
except ImportError:
    HAVE_SVGWRITE = False

from tqdm import tqdm


def check_svgwrite_installed() -> None:
    """
    Raise an IOError if svgwrite is not installed.
    """
    if not HAVE_SVGWRITE:
        raise IOError(
            "svg exporter not available because 'svgwrite' package is not installed. "
            "Use: pip install svgwrite"
        )


def edge_to_svg_polyline(
    topods_edge: TopoDS_Edge,
    tol: float = 0.1,
    unit: str = "mm"
) -> Tuple[svgwrite.shapes.Polyline, Bnd_Box2d]:
    """
    Convert a TopoDS_Edge to a svgwrite Polyline and compute its 2D bounding box.

    Parameters
    ----------
    topods_edge : TopoDS_Edge
        The edge to discretize and convert.
    tol : float, optional
        Discretization tolerance (default is 0.1).
    unit : str, optional
        The unit for scaling (default is "mm").
        Currently supported: 'mm', 'm'.

    Returns
    -------
    (polyline, box2d) : (svgwrite.shapes.Polyline, Bnd_Box2d)
        A tuple containing the generated Polyline and its bounding box.
    """
    check_svgwrite_installed()

    unit_factor = 1000.0 if unit == "m" else 1.0

    points_3d = discretize_edge(topods_edge, tol)
    points_2d = []
    box2d = Bnd_Box2d()

    for point in points_3d:
        # Take only the first two coordinates (x, y)
        x_p = -point[0] * unit_factor
        y_p = point[1] * unit_factor
        box2d.Add(gp_Pnt2d(x_p, y_p))
        points_2d.append((x_p, y_p))

    return svgwrite.shapes.Polyline(points_2d, fill="none"), box2d


def export_shape_to_svg(
    shape: TopoDS_Shape,
    filename: Optional[str] = None,
    width: int = 800,
    height: int = 600,
    margin_left: int = 10,
    margin_top: int = 30,
    export_hidden_edges: bool = True,
    location: gp_Pnt = gp_Pnt(0, 0, 0),
    direction: gp_Dir = gp_Dir(1, 1, 1),
    color: str = "black",
    line_width: str = "1px",
    unit: str = "mm"
) -> str:
    """
    Export a TopoDS_Shape as an SVG file or return the SVG as a string.

    Parameters
    ----------
    shape : TopoDS_Shape
        The shape to export.
    filename : str, optional
        If provided, save the output to this file path. Otherwise, return an SVG string.
    width : int, optional
        SVG canvas width (default 800).
    height : int, optional
        SVG canvas height (default 600).
    margin_left : int, optional
        Left margin in pixels (default 10).
    margin_top : int, optional
        Top margin in pixels (default 30).
    export_hidden_edges : bool, optional
        Whether to include hidden edges as dashed lines (default True).
    location : gp_Pnt, optional
        A point to look from (default gp_Pnt(0,0,0)).
    direction : gp_Dir, optional
        Direction for the parallel projection (default gp_Dir(1,1,1)).
    color : str, optional
        Stroke color for visible edges (default "black").
    line_width : str, optional
        Line width for the edges (default "1px").
    unit : str, optional
        Unit for scaling, e.g. "mm" or "m" (default "mm").

    Returns
    -------
    svg_str : str
        The SVG content as a string if `filename` is not provided, otherwise
        returns 'True' if file is successfully saved.
    """
    check_svgwrite_installed()

    if shape.IsNull():
        raise ValueError("Shape is Null. Cannot export an empty shape.")

    # Get visible and hidden edges
    visible_edges, hidden_edges = get_sorted_hlr_edges(
        shape,
        position=location,
        direction=direction,
        export_hidden_edges=export_hidden_edges,
    )

    global_2d_bounding_box = Bnd_Box2d()
    polylines = []

    # Visible edges
    for edge in visible_edges:
        svg_line, edge_box2d = edge_to_svg_polyline(edge, 0.1, unit)
        polylines.append(svg_line)
        global_2d_bounding_box.Add(edge_box2d)

    # Hidden edges (dashed)
    if export_hidden_edges:
        for edge in hidden_edges:
            svg_line, edge_box2d = edge_to_svg_polyline(edge, 0.1, unit)
            svg_line.dasharray([0.5, 0.5])
            polylines.append(svg_line)
            global_2d_bounding_box.Add(edge_box2d)

    x_min, y_min, x_max, y_max = global_2d_bounding_box.Get()
    bb2d_width = x_max - x_min
    bb2d_height = y_max - y_min

    dwg = svgwrite.Drawing(filename, (width, height), debug=False)
    dwg.viewbox(
        x_min - margin_left,
        y_min - margin_top,
        bb2d_width + 2 * margin_left,
        bb2d_height + 2 * margin_top,
    )

    # Style and add polylines
    for polyline in polylines:
        polyline.stroke(color, width=line_width, linecap="round")
        dwg.add(polyline)

    if filename is not None:
        dwg.save()
        if not os.path.isfile(filename):
            raise IOError(f"SVG export failed for {filename}")
        return "True"
    return dwg.tostring()


def _export_views_for_shape(step_dir: str, shape: TopoDS_Shape) -> None:
    """
    Helper function that exports the various views (iso, 100, 010, 001)
    for a given shape in a specified directory. Called with a timeout.
    """
    # iso.svg
    svg_path = os.path.join(step_dir, "iso.svg")
    export_shape_to_svg(
        shape,
        filename=svg_path,
        width=800,
        height=800,
        margin_left=2,
        margin_top=2,
        export_hidden_edges=False,
        location=gp_Pnt(0, 0, 0),
        direction=gp_Dir(1, 1, 1),  # isometric
        color="black",
        line_width="0.15px",
        unit="mm"
    )

    # 100.svg
    svg_path = os.path.join(step_dir, "100.svg")
    export_shape_to_svg(
        shape,
        filename=svg_path,
        width=800,
        height=800,
        margin_left=2,
        margin_top=2,
        export_hidden_edges=True,
        location=gp_Pnt(0, 0, 0),
        direction=gp_Dir(1, 0, 0),
        color="black",
        line_width="0.15px",
        unit="mm"
    )

    # 010.svg
    svg_path = os.path.join(step_dir, "010.svg")
    export_shape_to_svg(
        shape,
        filename=svg_path,
        width=800,
        height=800,
        margin_left=2,
        margin_top=2,
        export_hidden_edges=True,
        location=gp_Pnt(0, 0, 0),
        direction=gp_Dir(0, 1, 0),
        color="black",
        line_width="0.15px",
        unit="mm"
    )

    # 001.svg
    svg_path = os.path.join(step_dir, "001.svg")
    export_shape_to_svg(
        shape,
        filename=svg_path,
        width=800,
        height=800,
        margin_left=10,
        margin_top=10,
        export_hidden_edges=True,
        location=gp_Pnt(0, 0, 0),
        direction=gp_Dir(0, 0, 1),
        color="black",
        line_width="0.15px",
        unit="mm"
    )


def generate_iso_svg(root_folder: str) -> None:
    """
    Recursively walk through `root_folder`, locate .step/.stp files,
    and produce multiple SVG views. Each file's exports are subject
    to a 3-minute timeout. If it doesn't finish, skip that file.
    """
    step_file_list = glob.glob(os.path.join(root_folder, "**/*.step"), recursive=True)
    step_file_list += glob.glob(os.path.join(root_folder, "**/*.stp"), recursive=True)
    step_file_list.sort(reverse=True)

    for step_path in tqdm(step_file_list):
        step_dir = os.path.dirname(step_path)
        path_001_svg = os.path.join(step_dir, "001.svg")
        if os.path.isfile(path_001_svg):
            # If 001.svg already exists, skip generating any new SVGs
            continue
        
        file_size_bytes = os.path.getsize(step_path)
        if file_size_bytes > 4 * 1024 * 1024:
            print(f"[Skip] File too large (>4MB): {step_path}")
        else:
            # Read the shape
            shape = read_step_file(step_path, as_compound=True)

            # Use ThreadPoolExecutor with a timeout to avoid getting stuck
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                future = executor.submit(_export_views_for_shape, step_dir, shape)
                try:
                    future.result(timeout=60)  # 60 seconds = 1 minutes
                except concurrent.futures.TimeoutError:
                    
                    print(f"[Timeout] Skipping file after 1 minutes: {step_path}")
                except Exception as e:
                    print(f"[Error] Skipping file {step_path} due to error: {e}")


if __name__ == "__main__":
    generate_iso_svg("test_data")
 