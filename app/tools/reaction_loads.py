import plotly.graph_objects  as go
def plot_reaction(merged_df, load_case):
    print(f"{load_case=}")

    filtered_df = merged_df[merged_df["Output Case"] == load_case]
    print(filtered_df)
    FZ_min, FZ_max = filtered_df["FZ"].min(), filtered_df["FZ"].max()
    # Create plotly scatter plot
    fig = go.Figure(
        data=go.Scatter(
            x=filtered_df["Global X"],
            y=filtered_df["Global Y"],
            mode='markers+text',
            marker=dict(
                size=16,
                color=filtered_df["FZ"],
                colorscale=[
                    [0, "green"],
                    [0.5, "yellow"],
                    [1, "red"]
                ],
                colorbar=dict(title="FZ (kN)"),
                cmin=FZ_min,
                cmax=FZ_max
            ),
            text=[f"{fz:.1f}" for fz in filtered_df["FZ"]],
            textposition="top right"
        )
    )

    # Style the plot
    fig.update_layout(
        title=f"Heatmap for Output Case: {load_case}",
        xaxis_title="X (m)",
        yaxis_title="Y (m)",
        plot_bgcolor='rgba(0,0,0,0)',
    )
    fig.update_xaxes(
        linecolor='LightGrey',
        tickvals=filtered_df["Global X"],
        ticktext=[f"{x / 1000:.3f}" for x in filtered_df["Global X"]],
    )
    fig.update_yaxes(
        linecolor='LightGrey',
        tickvals=filtered_df["Global Y"],
        ticktext=[f"{y / 1000:.3f}" for y in filtered_df["Global Y"]],
    )
    fig.show()
    return fig