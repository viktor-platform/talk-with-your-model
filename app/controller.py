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
from app.models import Entities

import logging
import sys
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


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
    user_query = vkt.HiddenField(name="user_query", ui_name="user_query") 


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
            if isinstance(payload, list):
                payload = Entities(*payload)
            fig1 = plot_3d_scene(payload.nodes, payload.frames)

        # Process chat messages
        if params.user_query:
            try:
                messages = json.loads(params.user_query)
                if messages:
                    last_message = messages[-1]
                    # If the last message is from the user
                    if isinstance(last_message, dict) and "user" in last_message:
                        user_text = last_message["user"]
                        if payload:
                            # Memoize converts entities to list!
                            if isinstance(payload, list):
                                payload = Entities(*payload)
                            response = llm_response(user_text, ctx=payload.list_load_combos)
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
                                messages.append({"assistance": llm_message})
                            else:
                                raise ValueError("The LLM returned no parsed response.")
                        else:
                            # No file is uploaded
                            response = llm_response(user_text, ctx="No model uploaded!")
                            parsed_response = response.choices[0].message.parsed
                            if parsed_response:
                                messages.append({"assistance": parsed_response.response})
                            else:
                                raise ValueError("The LLM returned no parsed response.")


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