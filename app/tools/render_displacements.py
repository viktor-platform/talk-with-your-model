from app.tools.render_scene import compute_beam_vertices, add_beam_mesh
from app.models import Node, Frame, JoinDispDict
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import plotly.graph_objects as go  # type: ignore
import math
import numpy as np

import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def plot_3d_disp_scene(
    nodes: dict[str, Node],
    lines: dict[str, Frame],
    disp: JoinDispDict,
    output_case: str,
    sf: float = 50
) -> go.Figure:
    """
    """

    
    # Compute displaced node coordinates and store raw displacement magnitudes.
    disp_coords = {}   # key: node id (str), value: (x_disp, y_disp, z_disp)
    node_disp_mag = {} # key: node id (str), value: raw displacement magnitude (m)
    hover_texts = {}
    
    for node_id, node in nodes.items():
        # Default raw displacement.
        raw_dx = raw_dy = raw_dz = 0.0
        # Look up displacement from disp dictionary using integer node id.
        try:
            node_disp = disp.get(int(node_id), {}).get(output_case, [])
        except ValueError:
            node_disp = []
        if node_disp and len(node_disp) > 0:
            # Use the first DispEntry.
            d_entry = node_disp[0]
            raw_dx = d_entry["Ux"]
            raw_dy = d_entry["Uy"]
            raw_dz = d_entry["Uz"]
        # Scale the displacement for plotting the deformed shape.
        dx = raw_dx * sf
        dy = raw_dy * sf
        dz = raw_dz * sf
        new_x = node["x"] + dx
        new_y = node["y"] + dy
        new_z = node["z"] + dz
        disp_coords[node_id] = (new_x, new_y, new_z)
        # Compute raw displacement magnitude.
        raw_mag = math.sqrt(raw_dx**2 + raw_dy**2 + raw_dz**2)
        node_disp_mag[node_id] = raw_mag
        # Create hover text with raw displacements (in m).
        hover_texts[node_id] = (f"Node {node['id']}<br>"
                                f"Ux: {raw_dx:.4f} mm<br>"
                                f"Uy: {raw_dy:.4f} mm<br>"
                                f"Uz: {raw_dz:.4f} mm")
        logging.info(f"Node {node['id']}: original=({node['x']}, {node['y']}, {node['z']}), "
                     f"raw disp=({raw_dx}, {raw_dy}, {raw_dz}), "
                     f"scaled disp=({dx}, {dy}, {dz}), new=({new_x}, {new_y}, {new_z})")
    
    # Extract displaced node coordinates for setting axis limits.
    x_values = [coord[0] for coord in disp_coords.values()]
    y_values = [coord[1] for coord in disp_coords.values()]
    z_values = [coord[2] for coord in disp_coords.values()]
    
    # Compute axis limits with cubic aspect ratio.
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    z_min, z_max = min(z_values), max(z_values)
    x_range = x_max - x_min
    y_range = y_max - y_min
    z_range = z_max - z_min
    max_range = max(x_range, y_range, z_range)
    
    center_x = (x_max + x_min) / 2
    center_y = (y_max + y_min) / 2
    center_z = (z_max + z_min) / 2
    
    x_lim = [center_x - max_range / 2, center_x + max_range / 2]
    y_lim = [center_y - max_range / 2, center_y + max_range / 2]
    z_lim = [center_z - max_range / 2, center_z + max_range / 2]
    
    # Create the figure.
    fig = go.Figure()
    
    # Add node markers using displaced coordinates.
    fig.add_trace(go.Scatter3d(
        x=x_values,
        y=y_values,
        z=z_values,
        mode='markers',
        marker=dict(size=3, color='blue'),
        text=[hover_texts[node_id] for node_id in disp_coords],
        hoverinfo='text',
        showlegend=False
    ))
    
    # For each line, compute the average raw displacement magnitude from its two end nodes.
    line_disp = {}  # key: line id, value: average raw displacement magnitude (m)
    for line_id, frame in lines.items():
        nodeI = str(frame["nodeI"])
        nodeJ = str(frame["nodeJ"])
        mag1 = node_disp_mag.get(nodeI, 0.0)
        mag2 = node_disp_mag.get(nodeJ, 0.0)
        avg_disp = (mag1 + mag2) / 2
        line_disp[line_id] = avg_disp
        logging.info(f"Line {line_id}: nodeI raw disp={mag1:.4f} m, nodeJ raw disp={mag2:.4f} m, avg={avg_disp:.4f} m")
    
    # Compute global min and max raw displacement magnitudes for normalization.
    all_disp_vals = list(line_disp.values())
    min_disp = min(all_disp_vals)
    max_disp = max(all_disp_vals)
    logging.info(f"Raw displacement magnitude range: min={min_disp:.4f} m, max={max_disp:.4f} m")
    
    # Create normalization and get the jet colormap.
    norm = mcolors.Normalize(vmin=min_disp, vmax=max_disp)
    jet = cm.get_cmap("jet")
    
    # Render each line (beam) using the displaced coordinates and color them based on average raw displacement.
    for line_id, frame in lines.items():
        nodeI = str(frame["nodeI"])
        nodeJ = str(frame["nodeJ"])
        # Get displaced coordinates.
        A = np.array(disp_coords[nodeI])
        B = np.array(disp_coords[nodeJ])
        # Map average raw displacement to color.
        avg_disp = line_disp.get(line_id, 0.0)
        norm_val = norm(avg_disp)
        rgba = jet(norm_val)
        color = mcolors.to_hex(rgba)
        # Compute beam vertices and add beam mesh.
        vertices = compute_beam_vertices(A, B, width=300)
        add_beam_mesh(fig, vertices, color=color)
    
    # Add a dummy trace for the colorbar using raw displacement values.
    fig.add_trace(go.Scatter3d(
        x=[0, 0],
        y=[0, 0],
        z=[0, 0],
        mode='markers',
        marker=dict(
            color=[min_disp, max_disp],
            colorscale='jet',
            colorbar=dict(
                title="Disp (mm)",
            ),
            size=0,
            opacity=0,
            showscale=True
        ),
        showlegend=False,
        hoverinfo='none'
    ))
    
    # Define camera view.
    camera = dict(
        eye=dict(x=1.25, y=1.25, z=1.25)
    )
    
    fig.update_layout(
        scene=dict(
            camera=camera,
            xaxis=dict(
                range=x_lim,
                showticklabels=False,
                title='',
                showgrid=False,
                zeroline=False,
                showbackground=False,
                showspikes=False
            ),
            yaxis=dict(
                range=y_lim,
                showticklabels=False,
                title='',
                showgrid=False,
                zeroline=False,
                showbackground=False,
                showspikes=False
            ),
            zaxis=dict(
                range=z_lim,
                showticklabels=False,
                title='',
                showgrid=False,
                zeroline=False,
                showbackground=False,
                showspikes=False
            ),
            aspectmode="cube",
            bgcolor='white'
        ),
        paper_bgcolor='white',
        margin=dict(l=0, r=0, t=30, b=0)
    )
    
    return fig
