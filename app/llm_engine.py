import plotly.graph_objects as go #type: ignore
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ParsedChatCompletion
from typing import Any, Literal
from textwrap import dedent

from app.tools.render_scene import plot_3d_scene
from app.tools.render_internal_loads import (
    plot_3d_scene_with_forces,
    generater_station_point,
)
from app.tools.reaction_loads import plot_reaction
from app.tools.render_displacements import plot_3d_disp_scene
from app.tools.design_foundations import plot_foundations, plot_foundations_envelope
from app.models import Entities

load_dotenv()
client = OpenAI()


class Tool(BaseModel):
    pass


class PlotReactions(Tool):
    load_case: str | None = Field(
        ...,
        description = dedent("""Load case or combination to be plotted. If the user does 
        not provide one, assign one based on your context and ask the user to confirm it. 
        If there is no combination in the context, return None.""")
    )


class PlotModel(Tool):
    args: Literal["model"] = Field(
        ...,
        description = dedent("""Plots the structural model. Metadata such as deformation 
        and axial loads can also be plotted.""")
    )


class PlotDeformedShape(Tool):
    """Plots the deformed shape of the model for a selected load combo"""

    load_case: str | None = Field(
        ...,
        description = dedent("""Load case or combination for which the deformation or 
        displacements will be plotted.""")
    )
    scale_factor: float | None = Field(
        ...,
        description = dedent("""Optional. If the user wants to plot the deformation of 
        the model with a scale factor, this field can be used. Otherwise, set it to None.""")
    )


class PlotInternalForces(Tool):
    """Plots the internal loads of the model for a selected load combo"""

    load_case: str | None = Field(
        ...,
        description = dedent("""Load case or combination for which the internal loads 
        will be plotted. If the user does not provide one, assign one based on your 
        context and ask the user to confirm it.""")
    )
    force_component: Literal["P", "V1", "V2", "T", "M1", "M2", "M3"] = Field(
        ...,
        description = dedent("""Internal load or force component that the user wants to plot. 
        P is axial load, V1 is in-plane shear, V2 is out-of-plane shear, T is torsion, 
        M3 is the principal moment about the strong axis, M2 is the secondary moment, 
        and M1 is the wrap moment.""")
    )

class PadFoundationDesignForLoadCase(Tool):
    """Design Pad foundations based on reaction loads and soil preassure"""
    load_case: str | None = Field(
        ...,
        description = dedent("""Load case or combination for which the deformation or 
        displacements will be plotted.""")
    )
    soil_pressure: float = Field(
        ...,
        description = dedent("""Soil Pressure value, the user need to provide this values in kN/m2,
        remind the user about the units when using this tool!, use default 100kPa""")
    )

class PadFoundationDesignForLoadEnvelope(Tool):
    """Design Pad foundations based on the enveloped of the reaction loads and soil preassure."""
    soil_pressure: float = Field(
        ...,
        description = dedent("""Soil Pressure value, the user need to provide this values in kN/m2,
        remind the user about the units when using this tool!, use 100kPa as default""")
    )    

class Response(BaseModel):
    response: str
    selected_tool: (
        None | PlotModel | PlotReactions | PlotDeformedShape | PlotInternalForces | PadFoundationDesignForLoadCase | PadFoundationDesignForLoadEnvelope
    ) = Field(..., description="Select any of these tools, otherwise return None")


def llm_response(ctx: Any, conversation_history: list[dict]) -> ParsedChatCompletion[Response]:
    messages = []
    # Default system prompt is always first
    system_message = {
        "role": "system",
        "content": dedent(
            f"""You are a helpful assistant with the following context, who formats your responses nicely and helps answer questions about a structural model. Respond by describing the functionality of the tools you have without mentioning their names explicitly. If the context is empty, ask the user to upload an XLSX file of their ETABS model. These are the load cases/combinations from the model: {ctx}."""
        )
    }
    messages.append(system_message)
    # Append the conversation history as provided by the front end
    messages.extend(conversation_history)
    
    return client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=messages,
        response_format=Response,
    )

def execute_tool(response: Response, entities: Entities) -> tuple[str, go.Figure | None]:
    """Exectue the tools based on the user query and file_content. Generates a text response
    or a Plotly view."""

    if isinstance(response.selected_tool, PlotModel):
        if response.selected_tool.args == "model":
            return response.response, plot_3d_scene(entities.nodes, entities.frames)

    if isinstance(response.selected_tool, PlotReactions):
        if response.selected_tool.load_case:
            return response.response, plot_reaction(
                merged_data=entities.reactions_payloads, load_case=response.selected_tool.load_case
            )

    if isinstance(response.selected_tool, PlotDeformedShape):
        if response.selected_tool.load_case:
            return response.response, plot_3d_disp_scene(
                nodes=entities.nodes,
                lines=entities.frames,
                disp=entities.joints_disp,
                output_case=response.selected_tool.load_case,
                sf=80,
            )

    if isinstance(response.selected_tool, PlotInternalForces):
        if response.selected_tool.load_case:
            nodes, lines, new_comb_forces = generater_station_point(
                nodes=entities.nodes, lines=entities.frames, comb_forces=entities.internal_loads
            )
            return response.response, plot_3d_scene_with_forces(
                nodes=nodes,
                lines=lines,
                forces=new_comb_forces,
                load_case=response.selected_tool.load_case,
                force_component=response.selected_tool.force_component,
            )

    if isinstance(response.selected_tool, PadFoundationDesignForLoadCase):
        if response.selected_tool.load_case:
            return response.response, plot_foundations(
                merged_data=entities.reactions_payloads,
                bearing_pressure=response.selected_tool.soil_pressure,
                load_case=response.selected_tool.load_case,
            )

    if isinstance(response.selected_tool, PadFoundationDesignForLoadEnvelope):
        if response.selected_tool.soil_pressure:
            return response.response, plot_foundations_envelope(
                merged_data=entities.reactions_payloads,
                bearing_pressure=response.selected_tool.soil_pressure
            )

    return response.response, None

