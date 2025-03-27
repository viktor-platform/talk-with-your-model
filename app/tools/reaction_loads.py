import plotly.graph_objects  as go #type: ignore
from typing import Any

def plot_reaction(merged_data: list[dict[str, Any]], load_case: str) -> go.Figure:
    # Filter data based on load_case
    filtered_data = [row for row in merged_data if row.get("Output Case") == load_case]
    if not filtered_data:
        raise ValueError(f"No data found for load case {load_case}")

    # Determine FZ values range
    FZ_values = [row["FZ"] for row in filtered_data]
    FZ_min, FZ_max = min(FZ_values), max(FZ_values)
    # Extract x and y coordinates and create text labels for FZ values
    x_values = [row["Global X"] for row in filtered_data]
    y_values = [row["Global Y"] for row in filtered_data]
    text_values = [f"{row['FZ']:.1f}" for row in filtered_data]

    # Create plotly scatter plot
    fig = go.Figure(
        data=go.Scatter(
            x=x_values,
            y=y_values,
            mode='markers+text',
            marker=dict(
                size=16,
                color=FZ_values,
                colorscale=[
                    [0, "green"],
                    [0.5, "yellow"],
                    [1, "red"]
                ],
                colorbar=dict(title="FZ (kN)"),
                cmin=FZ_min,
                cmax=FZ_max
            ),
            text=text_values,
            textposition="top right"
        )
    )

    # Style the plot: reduce title size, center it, and adjust margins
    fig.update_layout(
        title=dict(
            text=f"Heatmap for Output Case: {load_case}",
            x=0.5,          # center the title
            font=dict(size=14)  # adjust title font size here
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