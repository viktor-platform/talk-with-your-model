import viktor as vkt  # type: ignore
import json
import plotly.graph_objects as go

from textwrap import dedent
from app.tools.render_scene import default_blank_scene
from app.llm_engine import llm_response, execute_tool
from app.tools.render_scene import plot_3d_scene
from app.parse_xlsx import get_entities
from app.models import Entities, memoize_corrector
from typing import Literal


def store_scene(figure: go.Figure, view_name: Literal["view"] = "view") -> None:
    """This function stores the output of a tool call in
    the vkt.Storage object. The storage object can be used to communicate
    between views."""
    vkt.Storage().set(
        view_name,
        data=vkt.File.from_data(figure.to_json().encode()),
        scope="entity",
    )


@memoize_corrector(Entities)
@vkt.memoize
def read_file_binary(file) -> Entities:
    """Memoized wrapper for processing the input .xlsx file.
    Returns:
        nodes_dict, frame_dicts, section_dicts, comb_forces_dict, joint_disp_dict, list_load_combs
    See app.models for data structure definitions.
    """
    xlsx_file = file.file
    file_content = xlsx_file.getvalue_binary()
    return Entities(*get_entities(file_content=file_content))


class Parametrization(vkt.Parametrization):
    upload_text = vkt.Text(
        dedent("""\
        # Talk With Your ETABS Model
        Export your model's results in `.xlsx` format from ETABS,
        click on the file loader below, and upload the `.xlsx` file.
        """)
    )
    chat = vkt.Chat("## AI Agent", method="call_llm")
    xlsx_file = vkt.FileField("**Upload a .xlsx file:**", flex=100)
    conversation_history = vkt.HiddenField(
        name="conversation_history", ui_name="conversation_history"
    )


class Controller(vkt.Controller):
    parametrization = Parametrization(width=35)

    def call_llm(self, params, **kwargs) -> vkt.ChatResult:
        """Multi-turn conversation between the user and the agent."""
        # Get conversation
        conversation_history = params.chat.get_messages()
        payload: None | Entities = None
        #  Check if user uploaded an Excel Field
        if params.xlsx_file:
            # Parse entities from the Excel
            entities = read_file_binary(params.xlsx_file)
            payload = entities
            # Create a 3D scene
            fig = plot_3d_scene(payload.nodes, payload.frames)
            # Save fig in memory this acts as hook to send the figure
            # to the PLotlyView
            store_scene(fig)

        # Conversation loop + function calls
        if conversation_history:
            try:
                if conversation_history[-1]["role"] == "user":
                    if payload:
                        # Send conversation history to the LLM
                        response = llm_response(
                            ctx=payload.model_context,
                            conversation_history=conversation_history,
                            file_status="File Uploaded",
                        )
                        # Process response
                        if response:
                            llm_message, generated_fig = execute_tool(
                                response=response, entities=payload
                            )
                            # Generated_fig is the output of a function call.
                            # If there is no function call execution, then it is None.
                            if generated_fig:
                                fig2 = generated_fig
                                # Store function call output in memory
                                store_scene(fig2)
                            return vkt.ChatResult(params.chat, llm_message)
                        else:
                            raise ValueError("The LLM returned no parsed response.")

                    # No payload -> No model ctx.
                    else:
                        response = llm_response(
                            conversation_history=conversation_history,
                            ctx="No model uploaded!",
                        )

                        if response:
                            return vkt.ChatResult(params.chat, response.response)
                        else:
                            raise ValueError("The LLM returned no parsed reponse.")

            except Exception as e:
                print(f"Error processing user query: {e}")

    @vkt.PlotlyView("Plotting Tool", width=100)
    def get_plotly_view(self, params, **kwargs) -> vkt.PlotlyResult:
        """This view plots the output of a tool call in a Plotly view.
        All tool calls are go.Figures exported as JSON. They are saved in
        Storage and retrieved here."""
        # 1. Delete tools calls from storage if there is no .xlsx file
        if not params.xlsx_file:
            entities = vkt.Storage().list(scope="entity")
            for entity in entities:
                if entity == "view":
                    vkt.Storage().delete("view", scope="entity")

        # 2. Try to get the previous view from the tool call, otherwise plot the model!
        try:
            raw = vkt.Storage().get("view", scope="entity").getvalue()
            fig = go.Figure(json.loads(raw))
        except Exception:
            # If there is no uploaded .xlsx file, then a blank view is plotted.
            if params.xlsx_file:
                # Parse entities from the Excel
                entities = read_file_binary(params.xlsx_file)
                payload = entities
                # Create a 3D scene for fig1
                fig = plot_3d_scene(payload.nodes, payload.frames)
            else:
                fig = default_blank_scene()

        return vkt.PlotlyResult(fig.to_json())
