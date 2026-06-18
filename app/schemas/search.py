from typing import Optional
from pydantic import BaseModel


class SearchResult(BaseModel):
    type: str
    id: int
    project_name: str
    snippet: str
