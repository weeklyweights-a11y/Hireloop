class HireLoopError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    detail: str = "Something went wrong"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class JobNotFoundError(HireLoopError):
    status_code = 404
    error_code = "JOB_NOT_FOUND"
    detail = (
        "Job not found. It may have been filled and removed from the career page."
    )


class RateLimitError(HireLoopError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    detail = "Rate limit exceeded. You can make 100 requests per hour. Try again later."


class RoleNotFoundError(HireLoopError):
    status_code = 404
    error_code = "ROLE_NOT_FOUND"
    detail = (
        "Role not found in the knowledge graph. Try a more common title "
        "(for example Backend Engineer), or use search_jobs."
    )


class SkillNotFoundError(HireLoopError):
    status_code = 404
    error_code = "SKILL_NOT_FOUND"
    detail = (
        "Skill not found in the knowledge graph. Check spelling, or search jobs "
        "with that skill via search_jobs."
    )


class CompanyNotFoundError(HireLoopError):
    status_code = 404
    error_code = "COMPANY_NOT_FOUND"
    detail = (
        "Company not found. Use list_companies to see monitored employers, "
        "or check the spelling."
    )


class GraphUnavailableError(HireLoopError):
    status_code = 503
    error_code = "GRAPH_UNAVAILABLE"
    detail = (
        "Market intelligence is temporarily unavailable (Neo4j). "
        "Job search and company browse still work."
    )


class InvalidRequestError(HireLoopError):
    status_code = 400
    error_code = "INVALID_REQUEST"
    detail = "Invalid request. Check required parameters and try again."

