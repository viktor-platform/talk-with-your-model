import io
import pandas as pd
from models import Node, Group, Frame, Section


def extract_sheets(file_content):
    sheet_names = [
        "Objects and Elements - Joints",
        "Group Assignments",
        "Beam Object Connectivity",
        "Frame Assigns - Sect Prop",
        "Element Joint Forces - Frame",
        "Column Object Connectivity",
    ]
    dataframes = {}
    # Create a BytesIO object from the file content
    if not isinstance(file_content, str):
        excel_data = io.BytesIO(file_content)
    else:    
        excel_data = file_content
    
    with pd.ExcelFile(excel_data) as excel_file:
        for sheet in sheet_names:
            dataframes[sheet] = pd.read_excel(excel_file, sheet_name=sheet, skiprows=1)
    return dataframes


def get_groups(file_content):
    sheet_name = "Group Assignments"
    excel_data = io.BytesIO(file_content)
    with pd.ExcelFile(excel_data) as excel_file:
        groups_df = pd.read_excel(excel_file, sheet_name=sheet_name, skiprows=1)
    groups_df_cleaned = groups_df.dropna(subset=["Group Name", "Object Unique Name"])
    group_names = groups_df_cleaned["Group Name"].unique().tolist()
    return group_names


def get_load_combos(file_content):
    sheet_name = ["Element Joint Forces - Frame"]
    if not isinstance(file_content, str):
        excel_data = io.BytesIO(file_content)
    else:
        excel_data = file_content
    with pd.ExcelFile(excel_data) as excel_file:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, skiprows=1)

    element_forces = df["Element Joint Forces - Frame"]
    df_combination = element_forces[element_forces["Case Type"] == "Combination"]

    combos = df_combination["Output Case"].unique().tolist()
    return combos


def get_entities(file_content)->tuple[dict[int, Node], dict[int, Frame], dict[int, Section], dict]:
    nodes_dict = {}
    frame_dicts = {}
    section_dicts = {}
    sheets_data = extract_sheets(file_content)

    joints_df = sheets_data["Objects and Elements - Joints"]
    beam_df = sheets_data["Beam Object Connectivity"]
    column_df = sheets_data["Column Object Connectivity"]
    frame_assigns_summary_df = sheets_data["Frame Assigns - Sect Prop"]
    element_forces = sheets_data["Element Joint Forces - Frame"]

    # Create Nodes
    joints_df_cleaned = joints_df.dropna(subset=["Object Name", "Global X", "Global Y", "Global Z", "Object Type"])
    for _, row in joints_df_cleaned.iterrows():
        if row["Object Type"] == "Joint":
            node_id = int(row["Object Name"])
            x = float(row["Global X"])
            y = float(row["Global Y"])
            z = float(row["Global Z"])
            node = Node(id=node_id, x=x, y=y, z=z)
            nodes_dict.update({node_id: node.model_dump()})


    # Create Frames
    column_df_cleaned = column_df.dropna(subset=["Unique Name", "UniquePtI", "UniquePtJ"])
    for _, row in column_df_cleaned.iterrows():
        if not isinstance(row["Unique Name"], str):  # avoid 'Global'
            frame_id = int(row["Unique Name"])
            nodeI = int(row["UniquePtI"])
            nodeJ = int(row["UniquePtJ"])
            frame = Frame(id=frame_id, nodeI=nodeI, nodeJ=nodeJ)
            frame_dicts.update({frame_id: frame.model_dump()})

    beam_df_cleaned = beam_df.dropna(subset=["Unique Name", "UniquePtI", "UniquePtJ"])
    for _, row in beam_df_cleaned.iterrows():
        if not isinstance(row["Unique Name"], str):  # avoid 'Global'
            frame_id = int(row["Unique Name"])
            nodeI = int(row["UniquePtI"])
            nodeJ = int(row["UniquePtJ"])
            frame = Frame(id=frame_id, nodeI=nodeI, nodeJ=nodeJ)
            frame_dicts.update({frame_id: frame.model_dump()})

    # Create sections
    frame_assigns_summary_df_cleaned = frame_assigns_summary_df.dropna(subset=["Section Property", "UniqueName"])
    section_names = frame_assigns_summary_df_cleaned["Section Property"].unique()

    for section_name in section_names:
        section_df = frame_assigns_summary_df_cleaned[
            frame_assigns_summary_df_cleaned["Section Property"] == section_name
        ]
        frame_ids = section_df["UniqueName"].tolist()
        section = Section(name=section_name, frame_ids=frame_ids)
        section_dicts.update({section_name: section.model_dump()})

    # Combos
    df_combination = element_forces[element_forces["Case Type"] == "Combination"]

    comb_forces_dict = {}
    # Group the DataFrame by 'Unique Name', 'Output Case', and 'Joint'
    grouped = df_combination.groupby(["Unique Name", "Output Case", "Joint"])
    for (unique_name, output_case, joint), group in grouped:
        if unique_name not in comb_forces_dict:
            comb_forces_dict[unique_name] = {}
        if output_case not in comb_forces_dict[unique_name]:
            comb_forces_dict[unique_name][output_case] = {}
        entries = []
        for idx, row in group.iterrows():
            entry = {
                "F1": row["F1"],
                "F2": row["F2"],
                "F3": row["F3"],
                "M1": row["M1"],
                "M2": row["M2"],
                "M3": row["M3"],
            }
            entries.append(entry)
        comb_forces_dict[unique_name][output_case][joint] = entries

    return nodes_dict, frame_dicts, section_dicts, comb_forces_dict


def get_section_by_id(sections, section_id):
    for section_name, section_vals in sections.items():
        if section_id in section_vals["frame_ids"]:
            return section_name


def process_etabs_file(file_content):
    # Read the file into a dataframe
    sheet_names = ["Joint Reactions", "Objects and Elements - Joints"]

    if not isinstance(file_content, str):
        excel_data = io.BytesIO(file_content)
    else:
        excel_data = file_content
    with pd.ExcelFile(excel_data) as excel_file:
        dataframes = pd.read_excel(excel_file, sheet_name=sheet_names, skiprows=1)

    # Process the 'Joint Reactions' dataframe
    loads_df = dataframes["Joint Reactions"].dropna(subset=["Unique Name", "Output Case"]).copy()

    # Process the 'Objects and Elements - Joints' dataframe
    cords = dataframes["Objects and Elements - Joints"].dropna(
        subset=["Element Name", "Object Name", "Global X", "Global Y", "Global Z"]
    ).copy()
    cords = cords.rename(columns={"Object Name": "Unique Name"})

    # Get unique load case names as a list
    unique_output_cases = loads_df["Output Case"].unique().tolist()

    # Merge loads and cords dataframe
    merged_df = pd.merge(loads_df, cords, on="Unique Name", how="inner")

    return unique_output_cases, merged_df.reset_index(drop=True)
