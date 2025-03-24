import viktor as vkt # type: ignore
import base64
import os
import json
from typing import Any
from pathlib import Path
from textwrap import dedent

from app.parse_xlsx import get_load_combos
from app.tools.render_scene import default_blank_scene
from app.llm_engine import llm_response, execute_tool

def read_file_binary(file) -> Any:
    xlsx_file = file.file
    file_content = xlsx_file.getvalue_binary()
    # nodes, frames, sections, loads = get_entities(file_content)
    combos = get_load_combos(file_content)
    return file_content, combos

class Parametrization(vkt.Parametrization):
    upload_text = vkt.Text(
        dedent(
            """
            # **Upload Your ETABS Model**\n
            Export your model's results in `.xlsx` format from ETABS,\n
            click on the file loader below, and upload the `.xlsx` file.
        """
        )
    )


    xlsx_file = vkt.FileField(
        "**Upload a .xlsx file:**",
        flex=50,
    )

    user_query = vkt.HiddenField(name="user_query", ui_name="user_query") 

class Controller(vkt.Controller):
    parametrization = Parametrization(width=30)

    @vkt.WebView('Web View')
    def app_view(self, params, **kwargs):
        fig = None
        messages = []
        # Default scene!

        if params.user_query:
            try:
                messages = json.loads(params.user_query)
                # Extract the user message content from the last message.
                last_message = messages[-1]
                if isinstance(last_message, dict) and "user" in last_message:
                    user_text = last_message["user"]

                    if params.xlsx_file:
                        file_content, combos = read_file_binary(params.xlsx_file)
                        response = llm_response(user_text, ctx=combos)
                        parsed_response = response.choices[0].message.parsed
                        llm_message, fig = execute_tool(response=parsed_response, file_content=file_content)
                        # Append backend response as a dict with key "assistance"
                        messages.append({"assistance": llm_message})
                    else:
                        response = llm_response(user_text, ctx="No model is uploaded, Please do it!")
                        parsed_response = response.choices[0].message.parsed
                        messages.append({"assistance": parsed_response.response})
                else:
                    user_text = last_message
                    
            except Exception as e:
                print(f"Error processing the request: {e}")

        html_path = Path(__file__).parent / 'canvas.html'
        html = html_path.read_text()

        if not fig:
            fig = default_blank_scene()

        plotly_scene_json = fig.to_json()
        plotly_json_base64 = base64.b64encode(plotly_scene_json.encode()).decode()

        messages_json = json.dumps(messages)
        messages_json_base64 = base64.b64encode(messages_json.encode()).decode()

        html = html.replace("PLOTLY_JSON", plotly_json_base64)
        html = html.replace("MESSAGES_JSON", messages_json_base64)
        html = html.replace("VIKTOR_JS_SDK", os.environ["VIKTOR_JS_SDK_PATH"] + "v1.js")

        return vkt.WebResult(html=html)