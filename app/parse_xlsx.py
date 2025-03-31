import io
import pandas as pd  # type: ignore

from typing import IO, Any
from app.models import (
    Node,
    Frame,
    Section,
    CombForcesDict,
    ForceEntry,
    DispEntry,
    JoinDispDict,
)


sheet_names = [
    "Objects and Elements - Joints",
    "Group Assignments",
    "Beam Object Connectivity",
    "Frame Assigns - Sect Prop",
    "Element Joint Forces - Frame",
    "Column Object Connectivity",
    "Element Forces - Beams",
    "Element Forces - Columns",
    "Joint Displacements",
    "Joint Reactions",
    "Modal Periods And Frequencies",
    "Material List by Section Prop"
]



def extract_sheets(file_content: str | bytes, sheet_name=sheet_names) -> dict[str, pd.DataFrame]:
    """Extract the relevant sheets from the uploaded file."""
    dataframes: dict[str, pd.DataFrame] = {}
    excel_data: str | IO[bytes]

    # For testing excel data is a path for prod is IO[bytes]
    if isinstance(file_content, str):
        excel_data = file_content
    else:
        excel_data = io.BytesIO(file_content)

    with pd.ExcelFile(excel_data) as excel_file:
        for sheet in sheet_names:
            dataframes[sheet] = pd.read_excel(excel_file, sheet_name=sheet, skiprows=1)
    return dataframes


def get_load_combos(sheets_data: dict[str, pd.DataFrame]) -> list[str]:
    """Reads the file content, creates a DataFrame and get a list of load combos."""
    sheet_name = "Element Joint Forces - Frame"
    # Create load combos list.
    element_forces = sheets_data[sheet_name]
    df_combination = element_forces[element_forces["Case Type"] == "Combination"]
    combos = df_combination["Output Case"].unique().tolist()
    return combos


def get_internal_loads(sheets_data: dict[str, pd.DataFrame]) -> CombForcesDict:
    """Read the pd.DataFrame and returns P, V2, V3, T, M2, M3 for each load combo and for each frame id"""
    beam_sheet_name = "Element Forces - Beams"
    columns_sheet_name = "Element Forces - Columns"
    df_beams = sheets_data[beam_sheet_name]
    df_columns = sheets_data[columns_sheet_name]
    # Combine columsn and beam dfs.
    element_forces = pd.concat([df_beams, df_columns], ignore_index=True)
    df_combination = element_forces[element_forces["Case Type"] == "Combination"]
    # Stores the load in a typedict
    comb_forces_dict: CombForcesDict = {}
    # Group the DataFrame by 'Unique Name', 'Output Case', and 'Joint'
    grouped = df_combination.groupby(["Unique Name", "Output Case", "Station"])
    for (unique_name, output_case, station), group in grouped:
        unique_name = str(int(unique_name))
        if unique_name not in comb_forces_dict:
            comb_forces_dict[unique_name] = {}
        if output_case not in comb_forces_dict[unique_name]:
            comb_forces_dict[unique_name][output_case] = {}
        entries = []
        for idx, row in group.iterrows():
            entry = ForceEntry(
                P=row["P"],
                V2=row["V2"],
                V3=row["V3"],
                T=row["T"],
                M2=row["M2"],
                M3=row["M3"],
            )
            entries.append(entry)
        comb_forces_dict[unique_name][output_case][station] = entries

    return comb_forces_dict


def get_entities(
    file_content: str | bytes,
) -> tuple[
    dict[str, Node],
    dict[str, Frame],
    dict[str, dict],
    CombForcesDict,
    JoinDispDict,
    list[str],
    list[dict[str, Any]]
]:
    """Process the file_content using `extract_sheets` and get a list of DataFrames
    that are use to get the entities of the model :Node, Frames, Frame Sections, Internal Loads"""
    # Output data models.
    nodes_dict: dict[str, Node] = {}
    frame_dicts: dict[str, Frame] = {}
    section_dicts: dict[str, dict] = {}
    comb_forces_dict: CombForcesDict  # Internal loads.
    joint_disp_dict: JoinDispDict  # Displacement
    list_load_combs: list[str]
    # Get the df for each entity from each.
    sheets_data: dict[str, pd.DataFrame] = extract_sheets(file_content)
    joints_df = sheets_data["Objects and Elements - Joints"]
    beam_df = sheets_data["Beam Object Connectivity"]
    column_df = sheets_data["Column Object Connectivity"]
    frame_assigns_summary_df = sheets_data["Frame Assigns - Sect Prop"]
    # 1. Create Nodes.
    joints_df_cleaned = joints_df.dropna(
        subset=["Object Name", "Global X", "Global Y", "Global Z", "Object Type"]
    )
    for _, row in joints_df_cleaned.iterrows():
        if row["Object Type"] == "Joint":
            node_id = int(row["Object Name"])
            x = float(row["Global X"])
            y = float(row["Global Y"])
            z = float(row["Global Z"])
            node = Node(id=node_id, x=x, y=y, z=z)
            nodes_dict.update({str(node_id): node})

    # 2.0 Create Frames.
    ## Join beam_df and column_df to avoid repetition.
    element_frames_df = pd.concat([column_df, beam_df], ignore_index=True)
    element_frames_df = element_frames_df.dropna(
        subset=["Unique Name", "UniquePtI", "UniquePtJ"]
    )
    for _, row in element_frames_df.iterrows():
        if not isinstance(row["Unique Name"], str):  # avoid 'Global'
            frame_id = int(row["Unique Name"])
            nodeI = int(row["UniquePtI"])
            nodeJ = int(row["UniquePtJ"])
            frame = Frame(id=frame_id, nodeI=nodeI, nodeJ=nodeJ)
            frame_dicts.update({str(frame_id): frame})
    # 3.0 Create sections.
    frame_assigns_summary_df_cleaned = frame_assigns_summary_df.dropna(
        subset=["Section Property", "UniqueName"]
    )
    section_names = frame_assigns_summary_df_cleaned["Section Property"].unique()
    ## Iterate over the sections.
    for section_name in section_names:
        section_df = frame_assigns_summary_df_cleaned[
            frame_assigns_summary_df_cleaned["Section Property"] == section_name
        ]
        frame_ids = section_df["UniqueName"].tolist()
        section = Section(name=section_name, frame_ids=frame_ids)
        section_dicts.update({section_name: section.model_dump()})
    # 4.0 Gets Member internal loads
    comb_forces_dict = get_internal_loads(sheets_data=sheets_data)
    # 5.0 Get displacements
    joint_disp_dict = get_displacements(sheets_data=sheets_data)
    # 6.0 Get load combos
    list_load_combs = get_load_combos(sheets_data=sheets_data)
    # 7.0 Get reactions loads and support coords.
    reaction_payload = process_etabs_file(data_sheet=sheets_data)
    # 8.0 Model Context
    model_context = get_model_ctx(data_sheet=sheets_data)

    return (
        nodes_dict,
        frame_dicts,
        section_dicts,
        comb_forces_dict,
        joint_disp_dict,
        list_load_combs,
        reaction_payload,
        model_context
    )


def get_displacements(sheets_data: dict[str, pd.DataFrame]) -> JoinDispDict:
    """
    Get the displacements from a DataFrame for each node.
    """
    # Sheet name.
    joint_disp_sheet_name = "Joint Displacements"
    # Get sheet data.
    df_jnt_disp = sheets_data[joint_disp_sheet_name]
    # Filter by "Combination".
    df_combination = df_jnt_disp[df_jnt_disp["Case Type"] == "Combination"]
    # Group the data.
    grouped = df_combination.groupby(["Unique Name", "Output Case"])
    # Data structure to stored displacement.
    joint_disp_dict: JoinDispDict = {}
    for (unique_name, output_case), group in grouped:
        # Due memoize this need to be converted first to int then to str!
        unique_name = str(int(unique_name))
        # Populate keys as nodes ids and create empty dict.
        if unique_name not in joint_disp_dict:
            joint_disp_dict[unique_name] = {}
        # Populate load cases and crates empty dict.
        if output_case not in joint_disp_dict[unique_name]:
            joint_disp_dict[unique_name][output_case] = []
        # Populate displacements entries
        entries: list[DispEntry] = []
        for idx, row in group.iterrows():
            entry = DispEntry(
                Ux=row["Ux"],
                Uy=row["Uy"],
                Uz=row["Uz"],
            )
            entries.append(entry)
        # Store displacements.
        joint_disp_dict[unique_name][output_case] = entries

    return joint_disp_dict

def get_modal_parameters(sheets_data: dict[str, 'pd.DataFrame']) -> str:
    # Select the appropriate sheet
    sheet_name = "Modal Periods And Frequencies"
    modal_df = sheets_data[sheet_name]
    # Define the markdown table header and separator rows
    header = "| Mode # | Period [s] | Frequency [Hz] |"
    separator = "| ------ | ---------- | -------------- |"
    # Start the table with header and separator
    rows = [header, separator]
    # Iterate over the DataFrame and add rows for indices greater than 1
    for index, row in modal_df.iterrows():
        if index > 0:
            mode_val = row["Mode"]
            period_val = round(row["Period"], 2)
            frequency_val = round(row["Frequency"], 2)
            rows.append(f"| {mode_val} | {period_val} | {frequency_val} |")
    # Join all rows into a single markdown string and return it
    markdown_table = "\n".join(rows)
    return markdown_table

def get_material_bill(sheets_data: dict[str, 'pd.DataFrame']) -> str:
    # Select the appropriate sheet
    sheet_name = "Material List by Section Prop"
    df = sheets_data[sheet_name]
    df = df.fillna("-")
    # Define the markdown table header and separator rows
    header = "| Section | Object Type | Number Pieces | Length (m) | Weight (kN) |"
    separator = "| ------- | ----------- | ------------- | ---------- | ----------- |"
    # Start the table with header and separator
    rows = [header, separator]
    # Iterate over the DataFrame and add rows for indices greater than 0
    for index, row in df.iterrows():
        if index > 0:
            section_val = row["Section"]
            object_type_val = row["Object Type"]
            number_pieces_val = row["Number Pieces"]
            if not isinstance(row["Length"], str):
                length_val = round(row["Length"],2)
                weight_val = round(row["Weight"],2)
            # Add a row to the table
            rows.append(
                f"| {section_val} | {object_type_val} | {number_pieces_val} | "
                f"{length_val} | {weight_val} | "
            )
    # Join all rows into a single markdown string
    markdown_table = "\n".join(rows)
    return markdown_table

def get_model_ctx(data_sheet: dict[str, pd.DataFrame])->str:
    """Get the model context from the xlsx file."""
    # Get modal table.
    modal_table = get_modal_parameters(data_sheet)
    # Get material bill table.
    material_bill = get_material_bill(data_sheet)
    # Get load combos.
    load_combos = get_load_combos(data_sheet)
    load_combos_str = "\n".join(f"{i+1}. {combo}" for i, combo in enumerate(load_combos))
    # Join all tables into a single markdown string.
    model_ctx = (
        f"### Modal Parameters\n{modal_table}\n\n"
        f"### Material Bill\n{material_bill}\n\n"
        f"### Load Combos\n{load_combos_str}\n"
    )
    return model_ctx


def process_etabs_file(data_sheet: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Get the reactions load and support node cords for tools usage!"""
    # Process the 'Joint Reactions' dataframe
    loads_df = data_sheet["Joint Reactions"].dropna(subset=["Unique Name", "Output Case"]).copy()

    # Process the 'Objects and Elements - Joints' dataframe
    cords = data_sheet["Objects and Elements - Joints"].dropna(
        subset=["Element Name", "Object Name", "Global X", "Global Y", "Global Z"]
    ).copy()
    cords = cords.rename(columns={"Object Name": "Unique Name"})

    # Merge loads and cords dataframe
    merged_df = pd.merge(loads_df, cords, on="Unique Name", how="inner")
    return merged_df.reset_index(drop=True).to_dict(orient="records")
