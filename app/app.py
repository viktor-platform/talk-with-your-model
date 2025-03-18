import pandas as pd

from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from time import time

from parse_xlsx import get_entities, get_load_combos, process_etabs_file
from tools.render_scene import plot_3d_scene
from tools.reaction_loads import plot_reaction
load_dotenv()
client = OpenAI()


class Tool(BaseModel):
    pass


class PlotlyTool(Tool):
    args: Literal["deformation", "axial_load", "response_spectrum"]


class TableTool(Tool):  
    args: Literal["reactions", "design_ratio",]

class GetLoadCombo(Tool):
    pass

class Response(BaseModel):
    response: str
    selected_tool: None | TableTool | PlotlyTool = Field(
        ..., description="Select any of these tools, otherwise return None"
    )


def llm_response(question: str, ctx: any):
    return client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a helpful assistant with the following context: Load combos: {ctx}."},
            {"role": "user", "content": f"Answer this question: {question}"},
        ],
        response_format=Response,
    )


if __name__ == "__main__":
    if False:
        excel_path = "small_model_clean.xlsx"
        nodes, frames, sections, loads = get_entities(excel_path)
        combos = get_load_combos(excel_path)

        plot_3d_scene(nodes=nodes, lines=frames)    

    # Reaction scenes 
    if True:

        _, merged_df = process_etabs_file("etabs_tutorial.xlsx")
        print(merged_df)
        plot_reaction(merged_df=merged_df, load_case="EQY")


    if False:
        response = llm_response(question="What are the load ", ctx = combos)
        response_instace = response.choices[0].message.parsed
        print(response_instace)

