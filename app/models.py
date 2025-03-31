from pydantic import BaseModel
from typing import TypedDict, NamedTuple, Any, Callable, TypeVar, Literal

class Node(TypedDict):
    id: int
    x: float
    y: float
    z: float


class Group(BaseModel):
    name: str
    frame_ids: list[int]


class AllGroups(BaseModel):
    groups: list[Group]


class Frame(TypedDict):
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

CombForcesDict = dict[UniqueName, dict[OutputCase, dict[Station, list[ForceEntry]]]]

# Type dict for the displacements
class DispEntry(TypedDict):
    Ux: float
    Uy: float
    Uz: float

JoinDispDict = dict[UniqueName, dict[OutputCase, list[DispEntry]]]

# Name tupled for entities 
class Entities(NamedTuple):
    nodes: dict[str, Node]
    frames: dict[str, Frame]
    sections: dict[str, dict]
    internal_loads: CombForcesDict
    joints_disp: JoinDispDict
    list_load_combos: list[str]
    reactions_payloads: list[dict[str, Any]]
    model_context: str

# For memoize -> convert list to tupples
T = TypeVar('T')
def memoize_corrector(entity: Callable[..., T]) -> Callable[[Callable[..., Any]], Callable[..., T]]:
    def decorator(fun: Callable[..., Any]) -> Callable[..., T]:
        def wrapped(*args, **kwargs) -> T:
            out = fun(*args, **kwargs)
            if isinstance(out, list):
                out = entity(*out)
            return out
        return wrapped
    return decorator

# Messge Model
class Messages(BaseModel):
    messages: list["Message"]

class Message(BaseModel):
    role: Literal["system", "user", "assistant"] 
    content: str