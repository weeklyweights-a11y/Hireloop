from pydantic import BaseModel, Field


class ResumeParseRequest(BaseModel):
    resume_text: str | None = None
    skills: list[str] | None = None
