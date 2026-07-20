from fastapi import APIRouter

from src.errors import InvalidRequestError
from src.schemas.resume import ResumeParseRequest
from src.services.resume_parse import parse_resume

router = APIRouter(tags=["resume"])


@router.post("/resume/parse")
def resume_parse(body: ResumeParseRequest) -> dict:
    if not body.resume_text and not body.skills:
        raise InvalidRequestError("Provide resume_text or skills.")
    try:
        return parse_resume(resume_text=body.resume_text, skills=body.skills)
    except Exception as e:
        raise InvalidRequestError(
            "Couldn't process this resume. Try pasting the text instead."
        ) from e
