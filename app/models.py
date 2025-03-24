from pydantic import BaseModel, Field
from typing import TypedDict

class Node(BaseModel):
    id: int
    x: float
    y: float
    z: float


class Group(BaseModel):
    name: str
    frame_ids: list[int]


class AllGroups(BaseModel):
    groups: list[Group]


class Frame(BaseModel):
    id: int
    nodeI: int
    nodeJ: int


class Section(BaseModel):
    name: str
    frame_ids: list[int]


class AllSections(BaseModel):
    sections: list[Section]

class InternalLoads(BaseModel):
    output_case: str


# Data Structure for the internal loads 
UniqueName = str
OutputCase = str
Station = str

# Define a TypedDict for a force entry.
class ForceEntry(TypedDict):
    P: float
    V2: float
    V3: float
    T: float
    M2: float
    M3: float

# Now, define the nested dictionary type using the aliases.
CombForcesDict = dict[UniqueName, dict[OutputCase, dict[Station, list[ForceEntry]]]]