# Talk with Your ETABS Model!

## Features

This app lets you talk to your ETABS models using AI. It includes an AI agent with several tools to:

- Query model results  
- Post-process results  
- Design components based on results  

### Query Results

You can ask the AI agent many questions like:

- "List all load combinations"  
- "What is the mass of the model?"  
- "What is the lowest modal period?"  

You can even ask what the agent can do! It can also generate visuals, as shown in the sample chat below:

![Internal Loads Tools](assets/TTM_GIF1.gif)

### Post-Process

You can not only ask for results but also process them. For example, you can make a heat map of the reaction loads, plot deformed shapes, or plot internal loads:

![Reaction Loads](assets/reactions_loads.JPG)

### Design Components

All model results are available to support design workflows. For example, the AI agent can help design pad foundations. It will ask for the soil bearing pressure and the load case, then suggest the foundation size. It can also calculate the required footing size:

![Foundation Tools](assets/foundation_tools.JPG)

## Technical Features

The app requires the OpenAI API. However, the agent is built with the [instructor](https://python.useinstructor.com/) framework, so it can be modified to work with [Anthropic](https://python.useinstructor.com/integrations/anthropic/).

An OpenAI API key is required and must be stored in a `.env` file (refer to `.env.example`). The app loads it through the `python-dotenv` module. Make sure not to share this API key, push it to any repository, or expose it to the public!

## Integration between the Llm and vkt.Views

1. `vkt.Chat` maintains the conversation. In its callback you retrieve the message history and send it to the LLM.  
2. The LLM returns either:  
   1. Plain text → update chat with `vkt.ChatResult(params.chat, text)`.  
   2. A structured function call with input arguments.  
3. For a function call:  
   1. Map arguments to the corresponding function in `app/tools`.  
   2. Execute the function to produce a Plotly figure.  
   3. Serialize the figure to JSON and save it via  
      ```python
      vkt.Storage().set("view", data=vkt.File.from_data(figure.to_json().encode()), scope="entity")
      ```  
4. The `@vkt.PlotlyView` method then:  
   1. Retrieves the JSON with  
      ```python
      raw = vkt.Storage().get("view", scope="entity").getvalue()
      ```  
   2. Reconstructs the figure using  
      ```python
      fig = go.Figure(json.loads(raw))
      ```  
   3. Returns `vkt.PlotlyResult(fig.to_json())` to render the view.  
5. The controller manages storage lifecycle—deleting or updating stored views when the input file changes or is removed.  

![workflow](assets/workflow.svg)