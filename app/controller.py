import viktor as vkt # type: ignore
import base64
import os
import json

from pathlib import Path
from textwrap import dedent

from app.tools.render_scene import default_blank_scene
from app.llm_engine import llm_response, execute_tool
from app.tools.render_scene import plot_3d_scene
from app.parse_xlsx import get_entities
from app.models import Entities, memoize_corrector


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
    xlsx_file = vkt.FileField("**Upload a .xlsx file:**", flex=50)
    conversation_history = vkt.HiddenField(name="conversation_history", ui_name="conversation_history") 


class Controller(vkt.Controller):
    parametrization = Parametrization(width=25)

    @vkt.WebView("Web View")
    def app_view(self, params, **kwargs)-> vkt.WebResult:
        # Default messages array
        messages = []
        # FIGURE 1: default black or blank scene
        fig1 = default_blank_scene()
        # FIGURE 2: default blank scene unless conditions are met
        fig2 = default_blank_scene()
        # Check if user uploaded an Excel file
        payload: None | Entities = None
        if params.xlsx_file:
            # Parse entities from the Excel
            entities = read_file_binary(params.xlsx_file)
            payload = entities
            # Create a 3D scene for fig1
            fig1 = plot_3d_scene(payload.nodes, payload.frames)

        # Process chat messages
        if params.conversation_history:
            try:
                conversation_history = json.loads(params.conversation_history)
                if conversation_history and conversation_history[-1]["role"] == "user":
                        if payload:
                            # Memoize converts entities to list!
                            response = llm_response(
                                ctx=payload.list_load_combos,
                                conversation_history=conversation_history
                            )
                            parsed_response = response.choices[0].message.parsed
                            if parsed_response:
                                # This might return a text response and a figure
                                llm_message, generated_fig = execute_tool(
                                    response=parsed_response,
                                    entities=payload
                                )
                                # Use the generated figure for fig2
                                if generated_fig is not None:
                                    fig2 = generated_fig

                                # Append the LLM response to messages
                                conversation_history.append({"role": "assistant", "content": llm_message})
                            else:
                                raise ValueError("The LLM returned no parsed response.")
                        else:
                            # No file is uploaded
                            response = llm_response(
                                conversation_history=conversation_history,
                                ctx="No model uploaded!",
                            )
                            parsed_response = response.choices[0].message.parsed
                            if parsed_response:
                                conversation_history.append({"role": "assistant", "content": parsed_response.response})
                            else:
                                raise ValueError("The LLM returned no parsed response.")

                messages = conversation_history
            except Exception as e:
                print(f"Error processing user query: {e}")

        # Load the HTML template
        html_path = Path(__file__).parent / "canvas.html"
        html = html_path.read_text()

        # Encode fig1 and fig2
        plotly_scene_json1 = fig1.to_json()
        plotly_scene_json2 = fig2.to_json()
        plotly_json_base64_1 = base64.b64encode(plotly_scene_json1.encode()).decode()
        plotly_json_base64_2 = base64.b64encode(plotly_scene_json2.encode()).decode()

        # Encode messages
        messages_json = json.dumps(messages)
        messages_json_base64 = base64.b64encode(messages_json.encode()).decode()

        # Replace placeholders
        html = html.replace("PLOTLY_JSON_SCENE_1", plotly_json_base64_1)
        html = html.replace("PLOTLY_JSON_SCENE_2", plotly_json_base64_2)
        html = html.replace("MESSAGES_JSON", messages_json_base64)
        html = html.replace("VIKTOR_JS_SDK", os.environ["VIKTOR_JS_SDK_PATH"] + "v1.js")

        return vkt.WebResult(html=html)