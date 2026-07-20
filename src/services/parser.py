from pydantic import BaseModel

from src.services.data_loader import DataLoader
from src.services.extractors.employment_type import extract_employment_type
from src.services.extractors.experience import extract_experience
from src.services.extractors.html import strip_html
from src.services.extractors.location import normalize_location
from src.services.extractors.remote import extract_remote_policy
from src.services.extractors.salary import extract_salary
from src.services.extractors.seniority import extract_seniority
from src.services.extractors.skills import extract_skills
from src.services.extractors.title import normalize_title, parse_title_components
from src.services.extractors.visa import extract_visa_sponsorship


class ParsedJob(BaseModel):
    salary_min: int | None = None
    salary_max: int | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    remote_policy: str = "unknown"
    location_city: str | None = None
    location_state: str | None = None
    location_country: str = "US"
    location_metro: str | None = None
    description_html: str = ""
    description_text: str = ""
    seniority: str | None = None
    title_normalized: str | None = None
    title_function: str | None = None  # not persisted
    # Components stripped from title_raw before fuzzy matching (title_raw unchanged)
    title_metadata: dict | None = None  # {"parenthetical": [...], "region": ..., "level": ...}
    title_department: str | None = None  # fills Job.department only when empty
    employment_type: str = "full_time"
    visa_sponsorship: str = "unknown"
    skills_required: list[str] = []
    skills_nice_to_have: list[str] = []


def parse_job(title: str, location: str | None, description: str | None) -> ParsedJob:
    data = DataLoader.get()
    description_html = description or ""
    description_text = strip_html(description_html)

    salary_min, salary_max = extract_salary(description_text)
    exp_min, exp_max = extract_experience(description_text)
    remote = extract_remote_policy(title, description_text, location)

    comps = parse_title_components(title)
    title_norm, title_fn = normalize_title(title, data.taxonomy)
    title_meta: dict = {}
    if comps.metadata:
        title_meta["parenthetical"] = comps.metadata
    if comps.region:
        title_meta["region"] = comps.region
    if comps.level:
        title_meta["level"] = comps.level
    seniority = extract_seniority(title, description_text)
    emp_type = extract_employment_type(title, description_text)
    visa = extract_visa_sponsorship(description_text)
    required, nice = extract_skills(description_text, data.skills)
    loc = normalize_location(location, data.locations)

    if loc.is_remote and remote in ("onsite", "unknown"):
        remote = "remote"

    return ParsedJob(
        salary_min=salary_min,
        salary_max=salary_max,
        experience_min=exp_min,
        experience_max=exp_max,
        remote_policy=remote,
        location_city=loc.city,
        location_state=loc.state,
        location_country=loc.country,
        location_metro=loc.metro_area,
        description_html=description_html,
        description_text=description_text,
        seniority=seniority,
        title_normalized=title_norm,
        title_function=title_fn,
        title_metadata=title_meta or None,
        title_department=comps.department,
        employment_type=emp_type,
        visa_sponsorship=visa,
        skills_required=required,
        skills_nice_to_have=nice,
    )
