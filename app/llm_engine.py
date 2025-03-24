from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any
from app.parse_xlsx import (
    get_entities,
    get_load_combos,
    process_etabs_file,
    get_internal_loads,
)
from app.tools.render_scene import plot_3d_scene
from app.tools.render_internal_loads import (
    plot_3d_scene_with_forces,
    generater_station_point,
)
from app.tools.reaction_loads import plot_reaction


load_dotenv()
client = OpenAI()


class Tool(BaseModel):
    pass


class PlotReactions(Tool):
    load_case: str | None = Field(
        ...,
        description="load case/combo to be plotted, if the user dont provide one, assign one based on your context and ask him back, if there is no combo in context return None",
    )


class PlotlyTool(Tool):
    args: Literal["model", "deformation", "axial_loads"] = Field(
        ...,
        description="Plots the structure model. Metadata can be ploted such as deformation, axial loads",
    )


class TableTool(Tool):
    args: Literal[
        "reactions",
        "design_ratio",
    ]


class GetLoadCombo(Tool):
    pass


class Response(BaseModel):
    response: str
    selected_tool: None | PlotlyTool | PlotReactions = Field(
        ..., description="Select any of these tools, otherwise return None"
    )


# Modal Participating Mass Ratios
# Material List by Section Prop
# Program Control


def read_file2(file) -> tuple:
    xlsx_file = file.file
    file_content = xlsx_file.getvalue_binary()
    nodes, frames, sections, loads = get_entities(file_content)
    combos = get_load_combos(file_content)
    return nodes, frames, sections, loads, combos


def llm_response(question: str, ctx: Any):
    print(f"{ctx}=")
    return client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"You are a helpful assistant with the following context: This are the load Cases/combos from the model = {ctx}.",
            },
            {"role": "user", "content": f"Answer this question: {question}"},
        ],
        response_format=Response,
    )


def execute_tool(response: Response, file_content):
    """Exectue the tools based on the user query and file_content"""
    print(f"{response.selected_tool=}")
    print(type(response.selected_tool))

    if isinstance(response.selected_tool, PlotlyTool):
        if response.selected_tool.args == "model":
            nodes, frames, sections, loads = get_entities(file_content)
            return response.response, plot_3d_scene(nodes, frames)

    if isinstance(response.selected_tool, PlotReactions):
        if response.selected_tool.load_case:
            _, merged_df = process_etabs_file(file_content)
            return response.response, plot_reaction(
                merged_df=merged_df, load_case=response.selected_tool.load_case
            )

    return response.response, None


if __name__ == "__main__":
    # Reaction scenes
    if False:
        _, merged_df = process_etabs_file("etabs_tutorial.xlsx")
        print(merged_df)
        plot_reaction(merged_df=merged_df, load_case="EQY")

    if False:
        response = llm_response(question="What are the load ", ctx="")
        response_instace = response.choices[0].message.parsed
        print(response_instace)

    test_plot_model = False
    if test_plot_model:
        excel_path = r"C:\Users\aleja\viktor-apps\Talk_with_etabs\test\Comercial Building ETABS.xlsx"
        response = llm_response(question="Plot the model", ctx="")
        parsed_response = response.choices[0].message.parsed
        print(f"{parsed_response=}")
        llm_message, tool_output = execute_tool(
            response=parsed_response, file_content=excel_path
        )
        if tool_output:
            print(tool_output)

    test_plot_reaction = False
    if test_plot_reaction:
        excel_path = r"C:\Users\aleja\viktor-apps\Talk_with_etabs\test\Comercial Building ETABS.xlsx"
        response = llm_response(
            question="Plot the reaction loads for load case Dead", ctx="Dead"
        )
        parsed_response = response.choices[0].message.parsed
        print(f"{parsed_response=}")
        llm_message, tool_output = execute_tool(
            response=parsed_response, file_content=excel_path
        )
        if tool_output:
            print(tool_output)

    test_internal_loads = True

    if test_internal_loads:
        excel_path = r"C:\Users\aleja\viktor-apps\Talk_with_etabs\test\Comercial Building ETABS.xlsx"
        beam_internal_loads = get_internal_loads(excel_path)
        nodes, frames, sections, loads = get_entities(excel_path)
        # Ploting internal loads.
        nodes, lines, new_comb_forces = generater_station_point(
            nodes=nodes, lines=frames, comb_forces=beam_internal_loads
        )
        fig = plot_3d_scene_with_forces(
            nodes=nodes,
            lines=lines,
            forces=new_comb_forces,
            load_case="1.0DL+1.0LL",
            force_component="M3",
        )
        fig.show()
