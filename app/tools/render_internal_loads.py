from app.tools.render_scene import compute_beam_vertices, add_beam_mesh
from app.models import Node, ForceEntry, Frame, CombForcesDict
from typing import Literal
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import plotly.graph_objects as go  # type: ignore
import math
import numpy as np

import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def aggregate_force_entries(
    force_list_a: list[ForceEntry], force_list_b: list[ForceEntry]
) -> ForceEntry:
    """
    For each force component, select the value (with its original sign)
    that has the maximum absolute magnitude from the two lists.
    """
    ForceKey = Literal["P", "V2", "V3", "T", "M2", "M3"]

    KEYS: tuple[ForceKey, ...] = ("P", "V2", "V3", "T", "M2", "M3")

    result: ForceEntry = {
        "P": 0.0,
        "V2": 0.0,
        "V3": 0.0,
        "T": 0.0,
        "M2": 0.0,
        "M3": 0.0,
    }
    for key in KEYS:
        candidates = [entry[key] for entry in force_list_a] + [
            entry[key] for entry in force_list_b
        ]
        result[key] = max(candidates, key=abs) if candidates else 0.0
    return result


def generater_station_point(
    nodes: dict[str, Node],
    lines: dict[str, Frame],
    comb_forces: CombForcesDict,
) -> tuple[dict[str, Node], dict[str, Frame], dict[str, dict]]:
    """
    Discretize each line by creating new inner nodes based on station values and aggregate force entries.
    Original comb_forces has the structure:
      dict[UniqueName, dict[OutputCase, dict[Station, list[ForceEntry]]]]
    The updated comb_forces (new_comb_forces) will have the structure:
      dict[UniqueName, dict[OutputCase, list[ForceEntry]]]
      comb_forces =! CombForcesDict (the first doesn't have stations keys)
    """
    # Determine current maximum node and line IDs.
    max_node_id = max(int(nid) for nid in nodes.keys())
    max_line_id = max(int(lid) for lid in lines.keys())

    # Get a load case from the first available key frame; we assume all load cases use the same station keys.
    first_key_frame = next(iter(comb_forces))
    first_load_case = next(iter(comb_forces[first_key_frame]))

    new_comb_forces: dict[str, dict] = {}

    # Work on a list of original line IDs because we will modify the lines dictionary.
    original_line_ids = list(lines.keys())

    for line_id in original_line_ids:
        line_args = lines[line_id]
        node_i = line_args["nodeI"]
        node_j = line_args["nodeJ"]

        # Get coordinates for the start and end nodes.
        node_i_coords = nodes[str(node_i)]
        node_j_coords = nodes[str(node_j)]

        # Calculate the direction vector and line length.
        dx = node_j_coords["x"] - node_i_coords["x"]
        dy = node_j_coords["y"] - node_i_coords["y"]
        dz = node_j_coords["z"] - node_i_coords["z"]
        line_length = math.sqrt(dx**2 + dy**2 + dz**2)
        if line_length == 0:
            logging.warning(f"Line {line_id} has zero length. Skipping discretization.")
            continue
        unit_dx = dx / line_length
        unit_dy = dy / line_length
        unit_dz = dz / line_length


        # Check if this line exists in comb_forces.
        if line_id not in comb_forces:
            logging.warning(f"Line {line_id} not found in comb_forces. Skipping.")
            continue
        station_dict = comb_forces[line_id][first_load_case]
        # Get station keys sorted by their numeric value.
        station_keys = list(station_dict.keys())
        sorted_station_keys = sorted(station_keys, key=lambda s: float(s))
        sorted_station_values = [float(s) for s in sorted_station_keys]

        if len(sorted_station_keys) < 2:
            logging.warning(f"Not enough station values for line {line_id}. Skipping.")
            continue

        # Remove the original line since it will be replaced by segments.
        del lines[line_id]

        # For each load case, compute an aggregated ForceEntry for each segment defined by adjacent stations.
        aggregated_forces_by_load: dict[str, list[ForceEntry]] = {}
        for load_case, station_data in comb_forces[line_id].items():
            seg_forces = []
            for i in range(len(sorted_station_keys) - 1):
                # Use the original sorted keys (as strings) to index the dictionary.
                key_a = sorted_station_keys[i]
                key_b = sorted_station_keys[i + 1]
                force_list_a = station_data[key_a]
                force_list_b = station_data[key_b]
                agg_force = aggregate_force_entries(force_list_a, force_list_b)
                seg_forces.append(agg_force)
            aggregated_forces_by_load[load_case] = seg_forces

        # Create new nodes only for the inner stations (skip the first and the last).
        new_node_ids: dict[
            int, int
        ] = {}  
        for idx in range(1, len(sorted_station_keys) - 1):
            station_val = sorted_station_values[idx]
            station_dist_mm = station_val 
            new_x = node_i_coords["x"] + station_dist_mm * unit_dx
            new_y = node_i_coords["y"] + station_dist_mm * unit_dy
            new_z = node_i_coords["z"] + station_dist_mm * unit_dz
            max_node_id += 1
            new_node_id = max_node_id
            nodes[str(new_node_id)] = {"id":new_node_id ,"x": new_x, "y": new_y, "z": new_z}
            new_node_ids[idx] = new_node_id

        # Create new segments. For segment i (0 <= i < len(sorted_station_keys)-1):
        num_segments = len(sorted_station_keys) - 1
        for i in range(num_segments):
            if i == 0:
                start_node = node_i
            else:
                start_node = new_node_ids[i]
            if (i + 1) in new_node_ids:
                end_node = new_node_ids[i + 1]
            else:
                end_node = node_j

            max_line_id += 1
            new_line_id = str(max_line_id)
            lines[new_line_id] = {"id":int(new_line_id),"nodeI": start_node, "nodeJ": end_node}

            # For each load case, assign the aggregated force entry corresponding to segment i.
            new_comb_forces[new_line_id] = {}
            for load_case, seg_forces in aggregated_forces_by_load.items():
                new_comb_forces[new_line_id][load_case] = [seg_forces[i]]

    logging.info("Discretization completed.")
    return nodes, lines, new_comb_forces


def plot_3d_scene_with_forces(
    nodes: dict[str, Node],
    lines: dict[str, Frame],
    forces: dict[str, dict],
    load_case: str,
    force_component: str,
) -> go.Figure:
    """
    Plot the expanded forces in the output station points
    """
    # Extract node coordinates.
    x_values = [node["x"] for node in nodes.values()]
    y_values = [node["y"] for node in nodes.values()]
    z_values = [node["z"] for node in nodes.values()]

    # Compute the min, max, and range for each axis.
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    z_min, z_max = min(z_values), max(z_values)
    x_range = x_max - x_min
    y_range = y_max - y_min
    z_range = z_max - z_min
    max_range = max(x_range, y_range, z_range)

    # Compute the center for each axis.
    center_x = (x_max + x_min) / 2
    center_y = (y_max + y_min) / 2
    center_z = (z_max + z_min) / 2

    # Define new limits with a cubic aspect ratio.
    x_lim = [center_x - max_range / 2, center_x + max_range / 2]
    y_lim = [center_y - max_range / 2, center_y + max_range / 2]
    z_lim = [center_z - max_range / 2, center_z + max_range / 2]

    # Create the figure.
    fig = go.Figure()

    # Add node markers.
    fig.add_trace(
        go.Scatter3d(
            x=x_values,
            y=y_values,
            z=z_values,
            mode="markers",
            marker=dict(size=3, color="blue"),
            text=[f"Node {node['id']}" for node in nodes.values()],
            hoverinfo="text",
            showlegend=False,
        )
    )

    # Determine the force value for each line.
    force_values = {}
    for line_id in lines.keys():
        if line_id in forces and load_case in forces[line_id]:
            # forces[line_id][load_case] is a list with one ForceEntry.
            force_entry = forces[line_id][load_case][0]
            value = force_entry.get(force_component, 0.0)
            force_values[line_id] = value
        else:
            force_values[line_id] = 0.0

    # Compute global min and max force values for normalization.
    all_force_vals = list(force_values.values())
    min_force = min(all_force_vals)
    max_force = max(all_force_vals)

    # Create a normalization and the jet colormap.
    norm = mcolors.Normalize(vmin=min_force, vmax=max_force)
    jet = cm.get_cmap("jet")

    # Render each frame as a beam with color based on force magnitude.
    for line_id, frame in lines.items():
        # Get the nodes for the frame.
        node1 = nodes[str(frame["nodeI"])]
        node2 = nodes[str(frame["nodeJ"])]

        A = np.array([node1["x"], node1["y"], node1["z"]])
        B = np.array([node2["x"], node2["y"], node2["z"]])

        # Determine the force value and map it to a color.
        force_val = force_values.get(line_id, 0.0)
        norm_val = norm(force_val)
        rgba = jet(norm_val)
        color = mcolors.to_hex(rgba)

        # Compute beam vertices and add the mesh with the computed color.
        vertices = compute_beam_vertices(A, B, width=300)
        add_beam_mesh(fig, vertices, color=color)

    # Add a dummy scatter trace for the colorbar.
    fig.add_trace(
        go.Scatter3d(
            x=[0, 0],
            y=[0, 0],
            z=[0, 0],
            mode="markers",
            marker=dict(
                color=[min_force, max_force],
                colorscale="jet",
                colorbar=dict(
                    title=f"{force_component} [kN]",
                ),
                size=0,
                opacity=0,
                showscale=True,
            ),
            showlegend=False,
            hoverinfo="none",
        )
    )

    # Define a camera view.
    camera = dict(eye=dict(x=1.25, y=1.25, z=1.25))

    fig.update_layout(
        scene=dict(
            camera=camera,
            xaxis=dict(
                range=x_lim,
                showticklabels=False,
                title="",
                showgrid=False,
                zeroline=False,
                showbackground=False,
                showspikes=False,
            ),
            yaxis=dict(
                range=y_lim,
                showticklabels=False,
                title="",
                showgrid=False,
                zeroline=False,
                showbackground=False,
                showspikes=False,
            ),
            zaxis=dict(
                range=z_lim,
                showticklabels=False,
                title="",
                showgrid=False,
                zeroline=False,
                showbackground=False,
                showspikes=False,
            ),
            aspectmode="cube",
            bgcolor="white",
        ),
        paper_bgcolor="white",
        margin=dict(l=0, r=0, t=30, b=0),
    )

    return fig
