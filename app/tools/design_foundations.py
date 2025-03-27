import plotly.graph_objects  as go #type: ignore

from collections import defaultdict
from typing import Any

def design_foundations(axial_loads: list[float], bearing_pressure: float, min_size: float = 1000) -> list[float]:
    """Calculates the pad size using soil bearing pressure"""
    pad_sizes: list[float] = []
    for axial_load in axial_loads:
        area = abs(axial_load) / bearing_pressure
        pad_size = round(area**0.5, 1)*1000
        pad_sizes.append(pad_size if pad_size > min_size else min_size)
    return pad_sizes

def plot_foundations(merged_data: list[dict[str, Any]], load_case: str, bearing_pressure: float) -> go.Figure:
    # Filter data based on load_case
    filtered_data = [row for row in merged_data if row.get("Output Case") == load_case]
    if not filtered_data:
        raise ValueError(f"No data found for load case {load_case}")

    FZ_values = [row["FZ"] for row in filtered_data]
    x_values = [row["Global X"] for row in filtered_data]
    y_values = [row["Global Y"] for row in filtered_data]

    # Compute pad sizes (in mm)
    pad_sizes = design_foundations(FZ_values, bearing_pressure)

    fig = go.Figure()

    for x, y, pad_size in zip(x_values, y_values, pad_sizes):
        half_size = pad_size / 2
        x0 = x - half_size
        x1 = x + half_size
        y0 = y - half_size
        y1 = y + half_size

        fig.add_shape(
            type="rect",
            x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(dash="dash", width=0.3, color="blue")
        )

        label_text = f"{pad_size/1000:.1f} x {pad_size/1000:.1f} m"
        fig.add_trace(go.Scatter(
            x=[x],
            y=[y],
            mode="text",
            text=[label_text],
            textposition="middle center",
            textfont=dict(size=9),
            showlegend=False
        ))

    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers",
        marker=dict(color="red", size=1),
        showlegend=False 
    ))

    fig.update_layout(
        title=dict(
            text=f"Foundation Pads for Load Case: {load_case}",
            font=dict(size=14)
        ),
        margin=dict(
            l=60,   # left margin
            r=60,   # right margin
            t=60,   # top margin
            b=60    # bottom margin
        ),
        xaxis_title="X (m)",
        yaxis_title="Y (m)",
        plot_bgcolor='rgba(0,0,0,0)',
    )
    fig.update_xaxes(
        linecolor='LightGrey',
        tickvals=x_values,
        ticktext=[f"{x / 1000:.3f}" for x in x_values],
    )
    fig.update_yaxes(
        linecolor='LightGrey',
        tickvals=y_values,
        ticktext=[f"{y / 1000:.3f}" for y in y_values],
    )
    return fig
def plot_foundations_envelope(merged_data: list[dict[str, Any]], bearing_pressure: float) -> go.Figure:
    """
    Plots foundation pads for the envelope of all load cases.
    It finds the maximum absolute FZ at each (x, y) location across all load cases,
    computes the required pad size for that maximum load, and plots the pads.
    """
    max_fz_dict: defaultdict = defaultdict(float)

    for row in merged_data:
        x = row["Global X"]
        y = row["Global Y"]
        fz_value = abs(row["FZ"])
        if fz_value > max_fz_dict[(x, y)]:
            max_fz_dict[(x, y)] = fz_value

    # Separate lists for x, y, and their corresponding max FZ
    x_values = []
    y_values = []
    FZ_values = []
    for (x_coord, y_coord), fz_val in max_fz_dict.items():
        x_values.append(x_coord)
        y_values.append(y_coord)
        FZ_values.append(fz_val)

    # Compute pad sizes (in mm) for the maximum loads
    pad_sizes = design_foundations(FZ_values, bearing_pressure)

    fig = go.Figure()

    for x, y, pad_size in zip(x_values, y_values, pad_sizes):
        half_size = pad_size / 2
        x0 = x - half_size
        x1 = x + half_size
        y0 = y - half_size
        y1 = y + half_size

        fig.add_shape(
            type="rect",
            x0=x0, y0=y0, x1=x1, y1=y1,
            line=dict(dash="dash", width=0.3, color="blut")
        )

        label_text = f"{pad_size/1000:.1f} x {pad_size/1000:.1f} m"
        fig.add_trace(go.Scatter(
            x=[x],
            y=[y],
            mode="text",
            text=[label_text],
            textposition="middle center",
            textfont=dict(size=9),
            showlegend=False
        ))

    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        mode="markers",
        marker=dict(color="red", size=1),
        showlegend=False
    ))

    fig.update_layout(
        title=dict(
            text="Foundation Pads for Load Combos Envelope",
            x=0.5,
            font=dict(size=14)
        ),
        margin=dict(
            l=60,   # left margin
            r=60,   # right margin
            t=60,   # top margin
            b=60    # bottom margin
        ),
        xaxis_title="X (m)",
        yaxis_title="Y (m)",
        plot_bgcolor='rgba(0,0,0,0)',
    )
    fig.update_xaxes(
        linecolor='LightGrey',
        tickvals=x_values,
        ticktext=[f"{x / 1000:.3f}" for x in x_values],
    )
    fig.update_yaxes(
        linecolor='LightGrey',
        tickvals=y_values,
        ticktext=[f"{y / 1000:.3f}" for y in y_values],
    )
    return fig
