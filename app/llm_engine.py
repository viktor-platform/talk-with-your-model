import plotly.graph_objects as go #type: ignore
import logging
import pprint

import instructor
from instructor.dsl.partial import PartialLiteralMixin
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ParsedChatCompletion
from typing import Any, Literal, Union
from textwrap import dedent

from app.tools.render_scene import plot_3d_scene
from app.tools.render_internal_loads import (
    plot_3d_scene_with_forces,
    generater_station_point,
)
from app.tools.reaction_loads import plot_reaction
from app.tools.render_displacements import plot_3d_disp_scene
from app.tools.design_foundations import plot_foundations, plot_foundations_envelope
from app.parse_xlsx import sheet_names
from app.models import Entities

# Logger to debug streaming responses
logger = logging.getLogger(__name__)
# Load .env variables.
load_dotenv()
# Patch OpenAI Client:
client = instructor.from_openai(OpenAI())

# Anthropic Client:
# import anthropic
# client = instructor.from_anthropic(create=anthropic.Anthropic())

class Tool(BaseModel):
    pass


class PlotReactions(Tool):
    load_case: Union[str , None] = Field(
        ...,
        description = dedent("""Load case or combination to be plotted. If the user does 
        not provide one, assign one based on your context and ask the user to confirm it. 
        If there is no combination in the context, return None.""")
    )


class PlotModel(Tool):
    args: str = Field(
        ...,
        description = dedent("""Plots the structural model. Metadata such as deformation 
        and axial loads can also be plotted.""")
    )


class PlotDeformedShape(Tool):
    """Plots the deformed shape of the model for a selected load combo"""

    load_case: Union[str, None] = Field(
        ...,
        description = dedent("""Load case or combination for which the deformation or 
        displacements will be plotted.""")
    )
    scale_factor: Union[float , None] = Field(
        ...,
        description = dedent("""Optional. If the user wants to plot the deformation of 
        the model with a scale factor, this field can be used. Otherwise, set it to None.""")
    )


class PlotInternalForces(Tool, PartialLiteralMixin):
    """Plots the internal loads of the model for a selected load combo"""

    load_case: Union[str , None] = Field(
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
    load_case: str = Field(
        ...,
        description = dedent("""Single Load case or combination for which the deformation or 
        displacements will be plotted.""")
    )
    soil_pressure: float = Field(
        ...,
        description = dedent("""Soil Pressure value, the user need to provide this values in kN/m2,
        remind the user about the units when using this tool!, use default 100kPa""")
    )

class PadFoundationDesignForLoadEnvelope(Tool):
    """Design Pad foundations based on the enveloped of the reaction loads and soil preassure for all load cases."""
    soil_pressure: float = Field(
        ...,
        description = dedent("""Soil Pressure value, the user need to provide this values in kN/m2,
        remind the user about the units when using this tool!, use 100kPa as default, """)
    )    
    tools_description: str = Field(..., description="Design Pad foundations based on the enveloped of the reaction loads and soil preassure for all load cases.")

class Response(BaseModel):
    response: str = Field(..., description="Be conversational firendly and Format the response always nicely in MARKDOWN, if the user haven't uploaded the file reminde him and list the required excel sheets!")
    selected_tool: (
        Union[None , PlotReactions , PlotDeformedShape , PlotInternalForces , PadFoundationDesignForLoadCase , PadFoundationDesignForLoadEnvelope]
    ) = Field(..., description="Select any of these tools, otherwise return None")


def llm_response(ctx: Any, conversation_history: list[dict],
                 file_status: str = "No File Uploaded",
                 required_sheets: list[str] = None,
                 verbose: bool = False) -> ParsedChatCompletion[Response]:
    if required_sheets is None:
        required_sheets = sheet_names  # Assuming sheet_names is defined globally

    messages = []
    # Default system prompt is always first
    system_message = {
        "role": "system",
        "content": dedent(
            f"""You are a helpful assistant with the following context, who formats your responses nicely and helps answer questions about a structural model.
            Respond by describing the functionality of the tools you have without mentioning their names explicitly.
            
            Important:
            If the file_status is 'No File Uploaded' or empty, ask the user to upload an XLSX file of their ETABS model with the following sheets: {required_sheets}. List the required sheets in MARKDOWN!. current file_status = {file_status}.

            If file_status is "File Uploaded" AND THE USER HAS NOT MADE ANY REQUEST, be friendly and thank them for uploading the file!

            This is the content from the model: {ctx}.
            
            FORMAT YOUR RESPONSES IN MARKDOWN!
            """
        )
    }
    messages.append(system_message)
    # Append the conversation history as provided by the front end
    messages.extend(conversation_history)
    
    # Optionally log the messages if verbose is enabled
    if verbose:
        logger.debug("Request messages:\n%s", pprint.pformat(messages))
    
    # Retrieve response chunks from the client
    resp_chunks = client.chat.completions.create_partial(
        model="gpt-4o",
        messages=messages,
        response_model=Response,
        temperature=0.5,
    )

    resp_final = None
    # Streaming
    for resp in resp_chunks:
        if verbose:
            logger.debug("Received response chunk:\n%s", resp)
        resp_final: Response = resp 

    return resp_final


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
