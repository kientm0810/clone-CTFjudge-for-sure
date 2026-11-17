from pydantic import BaseModel


class DocumentExtraction(BaseModel):
    filename: str
    content: str
    character_count: int
    paragraph_count: int
    table_count: int
