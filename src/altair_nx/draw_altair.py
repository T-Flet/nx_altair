import numpy as np
from numpy.typing import NDArray

import altair as alt
import networkx as nx

from copy import deepcopy

from .core import to_pandas_edges, to_pandas_edge_arrows, to_pandas_nodes


def draw_networkx_edges(G: nx.Graph = None, pos: dict[..., NDArray[np.float_]] = None,
    chart: alt.Chart = None, layer: alt.Chart = None, subset: list = None,
    width = 1, colour = 'grey', cmap: str = None, alpha = 1.,
    tooltip: list[str] = None, legend = False,
    loop_radius = .05, loop_angle = 90., loop_n_points = 30,
    curved_edges = False, control_points: list[tuple[float, float]] = None, interpolation = 'basis'):
    '''Draw the edges of graph G using Altair, with control over various features, including filtering and curve.

    Note that for arguments which accept edge attributes as alternatives to fixed values there are additional options generated in the drawing process:
    their name ('edge'), order of nodes ('order'), node pair names individually and together ('source', 'target', 'pair'), and node coordinates ('x', 'y').

    :param G: The graph to draw.
    :param pos: The node positions of G, as produced by any of the nx.*_layout functions, e.g. nx.kamada_kawai_layout,
        which is the default if pos is None (called with no edge attribute to use as weights, hence possibly missing out on more meaningful non-default positions).
        Note that most layouts use random seeds; for reproducible results set np.random.seed(...) before they are called.

    :param chart: A pre-existing chart to draw over.
    :param layer: A pre-existing chart layer to draw in.
    :param subset: Subset of edges to draw.

    :param width: Either an int or an edge attribute containing ints.
    :param colour: Either a colour string or an edge attribute containing colour strings if cmap is None and floats if not None.
    :param cmap: Colourmap for mapping intensities of edges (requires colour to be an edge attribute containing floats).
    :param alpha: Edge opacity.

    :param tooltip: Edge attributes to show on hover.
    :param legend: Whether to show a legend for attribute-controlled edge features.
    
    :param loop_radius: The radius of self-loop edges.
        Note that using too small a value may result in the nodes covering self-loops completely (interactive zoom may also cause this).
        Also note that changing the chart's aspect ratio outside of this function (with `.properties(width = ..., height = ...)`)
        will NOT rescale coordinates and will result in unequal x and y axes' units, deforming the loops to match the new aspect ratio;
        use the chart_width and chart_height arguments instead.
    :param loop_angle: The direction (in degrees) in which self-loops are drawn from the node; above it by default.
    :param loop_n_points: Number of points (INCLUDING the node itself) to draw self-loop edges.
        The default value is high in order to approximate a circle in both straight and curved edge drawing cases,
        HOWEVER, low values such as 2, 3, and 4 produce nice shapes pointed at the node in both cases
        (in the straight-edge case, respectively: a short segment, a triangle, and a square).
        NOTE: to draw straight edges but interpolation-curved loops (rather than by high manual point count), set control_points to [] rather than None
        (or really any list of points whose 2nd coordinate is 0).

    :param curved_edges: Whether edges should be curved (using control_points and interpolate arguments).
    :param control_points: The control points to use the interpolation method on; they should be expressed in coordinates relative to their straight edge:
        (proportion of edge length parallel to the edge, proportion of edge length perpendicular (anticlockwise) to the edge).
        E.g. the default value of [(.5, .1)] is a single control point halfway along the edge and .1 of its length to the left of it.
    :param interpolation: Interpolation method for curved edges (which are built on control points provided in edge-relative coordinates in curved_edges).
        The default interpolation is a cubic spline (i.e. 'basis').
        Interactive examples of possible values: https://altair-viz.github.io/user_guide/marks/line.html
        Corresponding descriptions: https://d3js.org/d3-shape/curve
        Recommendation:
            - 'basis', 'catmull-rom' and 'bundle' (and of course 'linear' and 'monotone') are best since they do not overshoot if control points are close to endpoints
            - the open and closed interpolation varieties are not appropriate for edges
            - the 'natural' cubic and 'cardinal' interpolations tend to overshoot for control points close to endpoints

    :return: An Altair chart of the edges of given graph.
    '''
    if curved_edges and control_points is None: control_points = [(.5, .1)]
    elif not curved_edges: control_points = None # Because to_pandas_edges relies only on control_points to know whether edges are supposed to be curved

    if layer is not None:
        df_edges = layer.data
        edge_chart = layer
    elif chart is not None:
        df_edges = chart.layer[0].data
        edge_chart = chart.layer[0]
    elif G is not None:
        if pos is None: pos = nx.drawing.layout.kamada_kawai_layout(G)
        df_edges = to_pandas_edges(G, pos, control_points = control_points, loop_radius = loop_radius, loop_angle = loop_angle, loop_n_points = loop_n_points)
        edge_chart = alt.Chart(df_edges)
    else: raise ValueError('one of G, chart or layer is required to draw.')

    marker_attrs, encoded_attrs = {}, {}
    legend = {} if legend else None


    # ---------- Handle the arguments ------------

    # Restrict to a given subset
    if isinstance(subset, list):
        df_edges = edge_chart.data = df_edges.loc[df_edges['pair'].isin(subset)]
    elif subset is not None: raise TypeError('subset must be a list or None.')

    # Width
    if isinstance(width, str): encoded_attrs['strokeWidth'] = alt.Size(width, legend = legend)
    elif isinstance(width, (float, int)): marker_attrs['strokeWidth'] = width
    else: raise TypeError('width must be a string or int.')

    # Colour
    if not isinstance(colour, str): raise TypeError('colour must be a string (either a colour or an edge attribute containing colour strings or floats for a colour map).')
    elif colour in df_edges.columns:
        if cmap is None: encoded_attrs['color'] = alt.Color(colour, legend = legend)
        elif isinstance(cmap, str):
            if df_edges.dtypes[colour] == 'O': raise TypeError(f'the edge attribute ({colour}) to use with cmap {cmap} is non-numeric.')
            else: encoded_attrs['color'] = alt.Color(colour, scale = alt.Scale(scheme = cmap), legend = legend)
        else: raise TypeError('cmap must be a string (colourmap name) or None.')
    else: marker_attrs['color'] = colour

    # Opacity
    if isinstance(alpha, str): encoded_attrs['opacity'] = alpha
    elif isinstance(alpha, (int, float)): marker_attrs['opacity'] = alpha
    elif alpha is not None: raise TypeError('alpha must be a string or None.')

    # Curved edges
    if curved_edges:
        if isinstance(interpolation, str): marker_attrs['interpolate'] = interpolation
        else: raise TypeError('interpolate must be a string.')
    
    # Tooltip
    if tooltip is not None: encoded_attrs['tooltip'] = tooltip


    # ---------- Construct the visualisation ------------

    edge_chart = edge_chart.mark_line(**marker_attrs).encode(
        x = alt.X('x', axis = alt.Axis(title = '', grid = False, labels = False, ticks = False)),
        y = alt.Y('y', axis = alt.Axis(title = '', grid = False, labels = False, ticks = False)),
        detail = 'edge', order = 'order', **encoded_attrs
    )

    if chart is not None: chart.layer[0] = edge_chart

    return edge_chart



def draw_networkx_arrows(G: nx.Graph = None, pos: dict[..., NDArray[np.float_]] = None,
    chart: alt.Chart = None, layer: alt.Chart = None, subset: list = None,
    width = 1, length = .1, length_is_relative = True,
    colour = 'grey', cmap: str = None, alpha = 1.,
    tooltip: list[str] = None, legend = False,
    curved_edges = False, control_points: list[tuple[float, float]] = None):
    '''Draw the edges of graph G using Altair, with control over various features, including filtering and curve.
    
    Note that for arguments which accept edge attributes as alternatives to fixed values there are additional options generated in the drawing process:
    their name ('edge'), order of nodes ('order'), node pair names individually and together ('source', 'target', 'pair'), and node coordinates ('x', 'y').

    :param G: The graph to draw.
    :param pos: The node positions of G, as produced by any of the nx.*_layout functions, e.g. nx.kamada_kawai_layout,
        which is the default if pos is None (called with no edge attribute to use as weights, hence possibly missing out on more meaningful non-default positions).
        Note that most layouts use random seeds; for reproducible results set np.random.seed(...) before they are called.

    :param chart: A pre-existing chart to draw over.
    :param layer: A pre-existing chart layer to draw in.
    :param subset: Subset of edges for which to draw arrows.

    :param width: Either an int or an edge attribute containing ints.
    :param length: A relative (i.e. proportion of edge length) or absolute measure of arrow length (the interpretation is determined by length_is_relative).
    :param length_is_relative: Whether arrow_length should be interpreted as a proportion of its edge length instead of an absolute measure.

    :param colour: Either a colour string or an edge attribute containing colour strings if cmap is None and floats if not None.
    :param cmap: Colourmap for mapping intensities of arrows (requires colour to be an edge attribute containing floats).
    :param alpha: Edge opacity.

    :param tooltip: Edge attributes to show on hover for arrows.
    :param legend: Whether to show a legend for attribute-controlled arrow features.

    :param curved_edges: Whether the edges for which arrows are to be drawn are curved.
    :param control_points: The control points used for the curved edges for which arrows are to be drawn are curved.

    :return: An Altair chart of the edges of given graph.
    '''
    if curved_edges and control_points is None: control_points = [(.5, .1)]
    elif not curved_edges: control_points = None # Because to_pandas_edge_arrows relies only on control_points to know whether edges are supposed to be curved

    if layer is not None:
        df_edge_arrows = layer.data
        edge_chart = layer
    elif chart is not None:
        df_edge_arrows = chart.layer[0].data
        edge_chart = chart.layer[0]
    elif G is not None:
        if pos is None: pos = nx.drawing.layout.kamada_kawai_layout(G)
        df_edge_arrows = to_pandas_edge_arrows(G, pos, length = length, length_is_relative = length_is_relative, control_points = control_points)
        edge_chart = alt.Chart(df_edge_arrows)
    else: raise ValueError('one of G, chart or layer is required to draw.')

    marker_attrs, encoded_attrs = {}, {}
    legend = {} if legend else None


    # ---------- Handle the arguments ------------

    # Restrict to a given subset
    if isinstance(subset, list):
        df_edge_arrows = edge_chart.data = df_edge_arrows.loc[df_edge_arrows['pair'].isin(subset)]
    elif subset is not None: raise TypeError('subset must be a list or None.')

    # Width
    if isinstance(width, str): encoded_attrs['size'] = alt.Size(width, legend = legend)
    elif isinstance(width, (float, int)): marker_attrs['strokeWidth'] = width
    else: raise TypeError('arrow_width must be a string or int.')

    # Colour
    if not isinstance(colour, str): raise TypeError('colour must be a string (either a colour or an edge attribute containing colour strings or floats for a colour map).')
    elif colour in df_edge_arrows.columns:
        if cmap is None: encoded_attrs['color'] = alt.Color(colour, legend = legend)
        elif isinstance(cmap, str):
            if df_edge_arrows.dtypes[colour] == 'O': raise TypeError(f'the edge attribute ({colour}) to use with cmap {cmap} is non-numeric.')
            else: encoded_attrs['color'] = alt.Color(colour, scale = alt.Scale(scheme = cmap), legend = legend)
        else: raise TypeError('cmap must be a string (colourmap name) or None.')
    else: marker_attrs['color'] = colour

    # Opacity
    if isinstance(alpha, str): encoded_attrs['opacity'] = alpha
    elif isinstance(alpha, (int, float)): marker_attrs['opacity'] = alpha
    elif alpha is not None: raise TypeError('alpha must be a string or None.')

    # Tooltip
    if tooltip is not None: encoded_attrs['tooltip'] = tooltip


    # ---------- Construct the visualisation ------------

    edge_chart = edge_chart.mark_line(**marker_attrs).encode(
        x = alt.X('x', axis = alt.Axis(grid = False, labels = False, ticks = False)),
        y = alt.Y('y', axis = alt.Axis(grid = False, labels = False, ticks = False)),
        detail = 'edge', **encoded_attrs
    )

    if chart is not None: chart.layer[0] = edge_chart

    return edge_chart



def draw_networkx_nodes(G: nx.Graph = None, pos: dict[..., NDArray[np.float_]] = None,
    chart: alt.Chart = None, layer: alt.Chart = None, subset: list = None,
    size: int | str = 400, outline_width: float | str = 1., shape = 'circle',
    colour = 'teal', cmap: str = None, alpha = 1.,
    tooltip: list[str] = None, legend = False):
    '''Draw the nodes of graph G using Altair, with control over various features, including filtering, and sizes.
    
    Note that for arguments which accept node attributes as alternatives to fixed values there are additional options generated in the drawing process:
    their name ('node') and position coordinates ('x', 'y').

    :param G: The graph to draw.
    :param pos: The node positions of G, as produced by any of the nx.*_layout functions, e.g. nx.kamada_kawai_layout,
        which is the default if pos is None (called with no edge attribute to use as weights, hence possibly missing out on more meaningful non-default positions).
        Note that most layouts use random seeds; for reproducible results set np.random.seed(...) before they are called.

    :param chart: A pre-existing chart to draw over.
    :param layer: A pre-existing chart layer to draw in.
    :param subset: Subset of nodes to draw.

    :param size: Either an int or a node attribute containing ints.
    :param outline_width: Either a single float for all nodes or a node attribute containing floats.
    :param shape: Either an Altair point-mark shape specifier or a node attribute containing the same.
        Note that this also includes SVG path strings; see https://altair-viz.github.io/user_guide/marks/point.html.

    :param colour: Either a colour string or a node attribute containing colour strings if cmap is None and floats if not None.
        Can also use '' to make nodes only outlines with no fill, but this makes summoning tooltips on hover difficult.
    :param cmap: Colourmap for mapping intensities of nodes (requires node_colour to be a node attribute containing floats).
    :param alpha: Node opacity.

    :param tooltip: Node attributes to show on hover.
    :param legend: Whether to show a legend for attribute-controlled node features.

    :return: An Altair chart of the nodes of the given graph.
    '''
    if layer is not None:
        df_nodes = layer.data
        node_chart = layer
    elif chart is not None:
        df_nodes = chart.layer[1].data
        node_chart = chart.layer[1]
    elif G is not None:
        if pos is None: pos = nx.drawing.layout.kamada_kawai_layout(G)
        df_nodes = to_pandas_nodes(G, pos)
        node_chart = alt.Chart(df_nodes)
    else: raise ValueError('one of G, chart or layer is required to draw.')

    marker_attrs, encoded_attrs = {}, {}
    legend = {} if legend else None


    # ---------- Handle the arguments ------------

    # Restrict to a given subset
    if isinstance(subset, list):
        df_nodes = node_chart.data = df_nodes.loc[subset]
    elif subset is not None: raise TypeError('node_subset must be a list or None.')

    # Size
    if isinstance(size, str): encoded_attrs['size'] = alt.Size(size, legend = legend)
    elif isinstance(size, int): marker_attrs['size'] = size
    else: raise TypeError('node_size must be a string or int.')
    
    # Width of lines
    if isinstance(outline_width, str): encoded_attrs['strokeWidth'] = alt.Size(outline_width, legend = legend)
    elif isinstance(outline_width, (float, int)): marker_attrs['strokeWidth'] = outline_width
    else: raise TypeError('linewidths must be a string or int.')
    
    # Shape
    if not isinstance(shape, str): raise TypeError('shape must be a string (either an altair point-mark shape or an edge attribute containing the same).')
    elif shape in df_nodes.columns: encoded_attrs['shape'] = alt.Shape(shape, legend = legend)
    else: marker_attrs['shape'] = shape

    # Colour
    if not isinstance(colour, str): raise TypeError('node_colour must be a string.')
    if colour in df_nodes.columns: encoded_attrs['fill'] = colour
    else: marker_attrs['fill'] = colour

    # Opacity
    if isinstance(alpha, str): encoded_attrs['opacity'] = alpha
    elif isinstance(alpha, (int, float)): marker_attrs['opacity'] = alpha
    elif alpha is not None: raise TypeError('alpha must be a string or None.')

    # Colour map
    if isinstance(cmap, str):
        encoded_attrs['fill'] = alt.Color(colour, scale = alt.Scale(scheme = cmap))
    elif cmap is not None: raise TypeError('cmap must be a string (colourmap name) or None.')

    # Tooltip
    if tooltip is not None: encoded_attrs['tooltip'] = tooltip


    # ---------- Construct the visualisation ------------

    node_chart = node_chart.mark_point(**marker_attrs).encode(
        x = alt.X('x', axis = alt.Axis(grid = False, labels = False, ticks = False)),
        y = alt.Y('y', axis = alt.Axis(grid = False, labels = False, ticks = False)),
        **encoded_attrs
    )

    if chart is not None: chart.layer[1] = node_chart

    return node_chart



def draw_networkx_labels(G: nx.Graph = None, pos: dict[..., NDArray[np.float_]] = None,
    chart: alt.Chart = None, layer: alt.Chart = None, subset: list = None,
    label: str = None, font_size = 15, font_colour = 'black'):
    '''Draw the node labels of graph G using Altair, with control over various features, including node filtering, and font.
    
    Note that for arguments which accept node attributes as alternatives to fixed values there are additional options generated in the drawing process:
    their name ('node') and position coordinates ('x', 'y').

    :param G: The graph to draw.
    :param pos: The node positions of G, as produced by any of the nx.*_layout functions, e.g. nx.kamada_kawai_layout,
        which is the default if pos is None (called with no edge attribute to use as weights, hence possibly missing out on more meaningful non-default positions).
        Note that most layouts use random seeds; for reproducible results set np.random.seed(...) before they are called.

    :param chart: A pre-existing chart to draw over.
    :param layer: A pre-existing chart layer to draw in.
    :param subset: Subset of nodes to draw.

    :param label: Either a string to use as identical label for all nodes or a node attribute containing strings.
        Note that the auto-generated 'node' attribute contains node names.
    :param font_size: Either an int or a node attribute containing ints.
    :param font_colour: Either a colour string or a node attribute containing colour strings.

    :return: An Altair chart of the node labels of the given graph.
    '''
    if layer is not None:
        df_nodes = layer.data
        node_chart = layer
    elif chart is not None:
        df_nodes = chart.layer[1].data
        node_chart = chart.layer[1]
    elif G is not None:
        if pos is None: pos = nx.drawing.layout.kamada_kawai_layout(G)
        df_nodes = to_pandas_nodes(G, pos)
        node_chart = alt.Chart(df_nodes)
    else: raise ValueError('one of G, chart or layer is required to draw.')

    marker_attrs, encoded_attrs = {}, {}


    # ---------- Handle the arguments ------------

    # Restrict to a given subset
    if isinstance(subset, list):
        df_nodes = node_chart.data = df_nodes.loc[subset]
    elif subset is not None: raise TypeError('node_subset must be a list or None.')

    # Text
    if not isinstance(label, str): raise TypeError('label must be a string.')
    if label in df_nodes.columns: encoded_attrs['text'] = label
    else: marker_attrs['text'] = label

    # Size
    if isinstance(font_size, str): encoded_attrs['size'] = alt.Size(font_size, legend = None)
    elif isinstance(font_size, int): marker_attrs['size'] = font_size
    else: raise TypeError('font_size must be a string or int.')

    # Colour
    if not isinstance(font_colour, str): raise TypeError('font_color must be a string.')
    if font_colour in df_nodes.columns: encoded_attrs['fill'] = font_colour
    else: marker_attrs['fill'] = font_colour


    # ---------- Construct the visualisation ------------

    node_chart = node_chart.mark_text(baseline = 'middle', **marker_attrs).encode(
        x = alt.X('x', axis = alt.Axis(grid = False, labels = False, ticks = False)),
        y = alt.Y('y', axis = alt.Axis(grid = False, labels = False, ticks = False)),
        **encoded_attrs
    )

    if chart is not None: chart.layer[1] = node_chart

    return node_chart



def draw_networkx(G: nx.Graph = None, pos: dict[..., NDArray[np.float_]] = None, chart: alt.Chart = None,
    node_subset: list = None, edge_subset: list = None, show_orphans = True, show_self_loops = True,
    node_size: int | str = 400, node_outline_width: float | str = 1., node_shape = 'circle', node_colour = 'teal', node_cmap: str = None, node_alpha = 1.,
    node_label: str = None, node_font_size = 15, node_font_colour = 'black', node_tooltip: list[str] = None, node_legend = False,
    edge_width = 1, edge_colour = 'grey', edge_cmap: str = None, edge_alpha = 1., edge_tooltip: list[str] = None, edge_legend = False,
    loop_radius = .05, loop_angle = 90., loop_n_points = 30,
    curved_edges = False, edge_control_points: list[tuple[float, float]] = None, edge_interpolation = 'basis',
    arrow_width = 2, arrow_length = .1, arrow_length_is_relative = True, arrow_colour = 'black', arrow_cmap: str = None, arrow_alpha = 1., arrow_legend = False,
    chart_width: float | None = 500., chart_height: float | None = 300.):
    '''Draw the graph G using Altair, with control over node, edge and arrow features, including filtering and curved edges.
    
    Note that for arguments which accept node or edge attributes as alternatives to fixed values there are additional options generated in the drawing process:
    for nodes these are their name ('node') and position coordinates ('x', 'y'),
    while for edges they are their name ('edge'), order of nodes ('order'), node pair names individually and together ('source', 'target', 'pair'), and node coordinates ('x', 'y').

    This function ensures that graph and chart aspect ratios always match by adapting one to the other or vice versa depending on whether one or none of chart_width and chart_height is None.
    For example, if all node coordinates (in pos) were along a thin rectangle, a square chart would not be ideal to draw them; this function will ensure that both are the same shape.
    Scaling issue context: although axes are not shown, any mismatch of chart and graph aspect ratios would result in unequal x and y axes' units;
    it is therefore best to avoid setting either or both sizes on the output chart (with `.properties(width = ..., height = ...)`) instead of using chart_width and chart_height,
    since this would deform coordinate-dependent shapes to the new aspect ratio
    (e.g. a (0,0)-(1,1) square would be drawn as a rectangle if width != height, while, say, node shapes themselves would be unaffected).

    :param G: The graph to draw.
    :param pos: The node positions of G, as produced by any of the nx.*_layout functions, e.g. nx.kamada_kawai_layout,
        which is the default if pos is None (called with no edge attribute to use as weights, hence possibly missing out on more meaningful non-default positions).
        Note that most layouts use random seeds; for reproducible results set np.random.seed(...) before they are called.
    :param chart: A pre-existing chart to draw over.

    :param node_subset: Subset of nodes to draw.
    :param edge_subset: Subset of edges to draw.
    :param show_orphans: Whether to draw nodes with no edges.
    :param show_self_loops: Whether to draw edges starting and ending on the same node;
        nodes with only self-loops will still be drawn (though edge-less) unless show_orphans is also False.
        
    :param node_size: Either an int or a node attribute containing ints.
    :param node_outline_width: Either a single float for all nodes or a node attribute containing floats.
    :param node_shape: Either an Altair point-mark shape specifier or a node attribute containing the same.
        Note that this also includes SVG path strings; see https://altair-viz.github.io/user_guide/marks/point.html.
    :param node_colour: Either a colour string or a node attribute containing colour strings if node_cmap is None and floats if not None.
         Can also use '' to make nodes only outlines with no fill, but this makes summoning tooltips on hover difficult.
    :param node_cmap: Colourmap for mapping intensities of nodes (requires node_colour to be a node attribute containing floats).
    :param node_alpha: Node opacity.
    
    :param node_label: Either a string to use as identical label for all nodes or a node attribute containing strings.
        Note that the auto-generated 'node' attribute contains node names.
    :param node_font_size: Either an int or a node attribute containing ints.
    :param node_font_colour: Either a colour string or a node attribute containing colour strings.
    :param node_tooltip: Node attributes to show on hover.
    :param node_legend: Whether to show a legend for attribute-controlled node features.

    :param edge_width: Either an int or an edge attribute containing ints.
    :param edge_colour: Either a colour string or an edge attribute containing colour strings if edge_cmap is None and floats if not None.
    :param edge_cmap: Colourmap for mapping intensities of edges (requires edge_colour to be an edge attribute containing floats).
    :param edge_alpha: Edge opacity.
    :param edge_tooltip: Edge attributes to show on hover.
    :param edge_legend: Whether to show a legend for attribute-controlled edge features.

    :param loop_radius: The radius of self-loop edges.
        Note that using too small a value may result in the nodes covering self-loops completely (interactive zoom may also cause this).
        Also note that changing the chart's aspect ratio outside of this function (with `.properties(width = ..., height = ...)`)
        will NOT rescale coordinates and will result in unequal x and y axes' units, deforming the loops to match the new aspect ratio;
        use the chart_width and chart_height arguments instead.
    :param loop_angle: The direction (in degrees) in which self-loops are drawn from the node; above it by default.
    :param loop_n_points: Number of points (INCLUDING the node itself) to draw self-loop edges.
        The default value is high in order to approximate a circle in both straight and curved edge drawing cases,
        HOWEVER, low values such as 2, 3, and 4 produce nice shapes pointed at the node in both cases
        (in the straight-edge case, respectively: a short segment, a triangle, and a square).
        NOTE: to draw straight edges but interpolation-curved loops (rather than by high manual point count), set control_points to [] rather than None
        (or really any list of points whose 2nd coordinate is 0).

    :param curved_edges: Whether edges should be curved (using control_points and interpolate arguments).
    :param edge_control_points: The control points to use the interpolation method on; they should be expressed in coordinates relative to their straight edge:
        (proportion of edge length parallel to the edge, proportion of edge length perpendicular (anticlockwise) to the edge).
        E.g. the default value of [(.5, .1)] is a single control point halfway along the edge and .1 of its length to the left of it.
    :param edge_interpolation: Interpolation method for curved edges (which are built on control points provided in edge-relative coordinates in curved_edges).
        The default interpolation is a cubic spline (i.e. 'basis').
        Interactive examples of possible values: https://altair-viz.github.io/user_guide/marks/line.html
        Corresponding descriptions: https://d3js.org/d3-shape/curve
        Recommendation:
            - 'basis', 'catmull-rom' and 'bundle' (and of course 'linear' and 'monotone') are best since they do not overshoot if control points are close to endpoints
            - the open and closed interpolation varieties are not appropriate for edges
            - the 'natural' cubic and 'cardinal' interpolations tend to overshoot for control points close to endpoints

    :param arrow_width: Either an int or an edge attribute containing ints.
    :param arrow_length: The proportion of the line to be occupied by the arrow.
    :param arrow_length_is_relative: Whether arrow_length should be interpreted as a proportion of its edge length instead of an absolute measure.
    :param arrow_colour: Either a colour string or an edge attribute containing colour strings if arrow_cmap is None and floats if not None.
    :param arrow_cmap: Colourmap for mapping intensities of arrows (requires arrow_colour to be an edge attribute containing floats).
    :param arrow_alpha: Arrow opacity.
    :param arrow_legend: Whether to show a legend for attribute-controlled arrow features.

    :param chart_width: Width to set the chart to (while maintaining equality between the drawn axes' units). Works in combination with chart_height:
        either size is allowed to be None (though not both), letting the graph's own aspect ratio determine the other;
        if both are not None, then the graph's aspect ratio is reshaped to the given one.
    :param chart_height: Height to set the chart to (while maintaining equality between the drawn axes' units). Works in combination with chart_width:
        either size is allowed to be None (though not both), letting the graph's own aspect ratio determine the other;
        if both are not None, then the graph's aspect ratio is reshaped to the given one.

    :return: An Altair chart of the given graph; its possible layers (`.layer`) are [edges, arrows, nodes, labels], in this order,
        but arrows are present only if G is directed and labels only if node_label is not None.
        Note: the node coordinates will be different from those in the input pos, as scaling takes place to ensure that graph and chart aspect ratios match
        (so that the x and y axes' units are equal);
        in particular, the shorter axis will have length of approximately 1
        (this is to ensure that the size of self-loops for a given loop_radius value is consistent relative to chart size).
        The new coordinates can be extracted from the dataframe of the node layer: `output.layer[index_of_node_layer].data`.
    '''

    if not (show_self_loops and show_orphans):
        G = deepcopy(G)
        if not show_self_loops: G.remove_edges_from(nx.selfloop_edges(G))
        if not show_orphans: G.remove_nodes_from(list(nx.isolates(G))) # wants a non-generator iterable
    
    if not pos: pos = nx.drawing.layout.kamada_kawai_layout(G)


    # ---------- Scale coordinates ------------

    if chart_width is None and chart_height is None: raise ValueError('chart_width and chart_height cannot both be None; if one is None then the other is determined by the graph\'s own aspect ratio.')

    pos_xs, pos_ys = zip(*pos.values())
    x_range, y_range = max(pos_xs) - min(pos_xs), max(pos_ys) - min(pos_ys)
    if chart_width is None: chart_width = chart_height * x_range / y_range
    if chart_height is None: chart_height = chart_width * y_range / x_range

    # Scale x and y to [0,1] (so that loop_radius values are consistent across charts)
    pos = {n: (0. if x_range == 0 else (xy[0] - min(pos_xs)) / x_range, 0. if y_range == 0 else (xy[1] - min(pos_ys)) / y_range) for n, xy in pos.items()}
    if chart_width != chart_height: # Stretch the coordinate corresponding to the larger chart size so that aspect ratios match (and therefore x and y axes' units are equal)
        pos = {n: (xy[0] * chart_width/chart_height, xy[1]) if chart_width >= chart_height else (xy[0], xy[1] * chart_height/chart_width) for n, xy in pos.items()}


    # ---------- Construct and assemble the layers ------------

    # Edges
    if len(G.edges):
        edges = draw_networkx_edges(G, pos, chart = chart, subset = edge_subset,
            width = edge_width, colour = edge_colour, cmap = edge_cmap, alpha = edge_alpha,
            tooltip = edge_tooltip, legend = edge_legend,
            loop_radius = loop_radius, loop_angle = loop_angle, loop_n_points = loop_n_points,
            curved_edges = curved_edges, control_points = edge_control_points, interpolation = edge_interpolation)

        # Arrows
        if nx.is_directed(G):
            arrows = draw_networkx_arrows(G, pos, chart = chart, subset = edge_subset,
                width = arrow_width, length = arrow_length, length_is_relative = arrow_length_is_relative,
                colour = arrow_colour, cmap = arrow_cmap, alpha = arrow_alpha,
                tooltip = edge_tooltip, legend = arrow_legend,
                curved_edges = curved_edges, control_points = edge_control_points)

    # Nodes
    if len(G.nodes):
        nodes = draw_networkx_nodes(G, pos, chart = chart, subset = node_subset,
            size = node_size, outline_width = node_outline_width, shape = node_shape,
            colour = node_colour, cmap = node_cmap, alpha = node_alpha,
            tooltip = node_tooltip, legend = node_legend)

        # Node labels
        if node_label:
            labels = draw_networkx_labels(G, pos, chart = chart, subset = node_subset,
                label = node_label, font_size = node_font_size, font_colour = node_font_colour)

    # Layer the chart
    viz = []
    if len(G.edges):
        viz.append(edges)
        if nx.is_directed(G): viz.append(arrows)

    if len(G.nodes):
        viz.append(nodes)
        if node_label: viz.append(labels)

    if viz: viz = alt.layer(*viz)
    else: raise ValueError('G does not contain any nodes or edges.')

    return viz.properties(width = chart_width, height = chart_height)


