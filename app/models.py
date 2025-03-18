
from pydantic import BaseModel

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
