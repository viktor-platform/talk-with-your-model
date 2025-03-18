from models import Node, Frame
import plotly.graph_objects as go
import numpy as np

def compute_beam_vertices(A, B, width=0.1):
    """
    Compute the eight vertices of a rectangular beam (prism) between endpoints A and B.
    The beam has a square cross-section with side 'width'.
    """
    v = B - A
    norm_v = np.linalg.norm(v)
    if norm_v == 0:
        raise ValueError("Zero length beam")
    v_hat = v / norm_v
    
    # Choose an arbitrary vector that is not parallel to v_hat.
    a = np.array([0, 0, 1])
    if abs(np.dot(v_hat, a)) > 0.99:
        a = np.array([0, 1, 0])
    
    # Compute two perpendicular vectors.
    cross1 = np.cross(v_hat, a)
    cross1 /= np.linalg.norm(cross1)
    cross2 = np.cross(v_hat, cross1)
    cross2 /= np.linalg.norm(cross2)
    
    half_width = width / 2
    cross1 *= half_width
    cross2 *= half_width

    # Compute vertices at A.
    v0 = A + cross1 + cross2
    v1 = A + cross1 - cross2
    v2 = A - cross1 - cross2
    v3 = A - cross1 + cross2
    # Compute vertices at B.
    v4 = B + cross1 + cross2
    v5 = B + cross1 - cross2
    v6 = B - cross1 - cross2
    v7 = B - cross1 + cross2

    vertices = np.array([v0, v1, v2, v3, v4, v5, v6, v7])
    return vertices

def add_beam_mesh(fig, vertices, color="teal"):
    """
    Add a Mesh3d trace representing a beam (rectangular prism) to the figure.
    Lighting parameters have been added to improve the visibility of thin beams.
    """
    # Define faces for the beam. Each quadrilateral is split into two triangles.
    faces = [
        (0, 1, 2, 3),  # end face at A
        (4, 5, 6, 7),  # end face at B
        (0, 1, 5, 4),  # side face 1
        (1, 2, 6, 5),  # side face 2
        (2, 3, 7, 6),  # side face 3
        (3, 0, 4, 7)   # side face 4
    ]
    
    i_list, j_list, k_list = [], [], []
    for a, b, c, d in faces:
        # First triangle.
        i_list.append(a)
        j_list.append(b)
        k_list.append(c)
        # Second triangle.
        i_list.append(a)
        j_list.append(c)
        k_list.append(d)
    
    # Extract x, y, z coordinates.
    x = vertices[:, 0]
    y = vertices[:, 1]
    z = vertices[:, 2]
    
    beam_trace = go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i_list,
        j=j_list,
        k=k_list,
        color=color,
        opacity=1.0,
        flatshading=True,
        showscale=False,
        hoverinfo='none',
        lighting=dict(ambient=0.5, diffuse=0.8, specular=0.3, roughness=0.9)
    )
    fig.add_trace(beam_trace)

def plot_3d_scene(nodes: dict[int, Node], lines: dict[int, Frame]) -> go.Figure:
    # Ensure each node is an instance of Node.
    for node_id, node in nodes.items():
        if not isinstance(node, Node):
            nodes[node_id] = Node(**node)
    
    # Extract node coordinates.
    x_values = [node.x for node in nodes.values()]
    y_values = [node.y for node in nodes.values()]
    z_values = [node.z for node in nodes.values()]
    
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
    fig.add_trace(go.Scatter3d(
        x=x_values,
        y=y_values,
        z=z_values,
        mode='markers',
        marker=dict(size=1, color='blue'),
        text=[f"Node {node.id}" for node in nodes.values()],
        hoverinfo='text'
    ))
    
    # Render each frame as a beam using keys "nodeI" and "nodeJ".
    for frame in lines.values():
        node1 = nodes[frame["nodeI"]]
        node2 = nodes[frame["nodeJ"]]
        
        A = np.array([node1.x, node1.y, node1.z])
        B = np.array([node2.x, node2.y, node2.z])
        
        vertices = compute_beam_vertices(A, B, width=300)
        add_beam_mesh(fig, vertices, color="teal")
    
    # Define a camera view.
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
    
    fig.show()
    return fig
