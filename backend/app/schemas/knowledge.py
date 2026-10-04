from pydantic import BaseModel, Field


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    equipment_type: str | None = Field(default=None, max_length=40)
    top_k: int = Field(default=4, ge=1, le=10)
