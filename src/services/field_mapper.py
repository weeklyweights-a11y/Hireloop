import re

from pydantic import BaseModel

_INDEXED = re.compile(r"^(\w+)\[(\d+)\]$")


class MappedJob(BaseModel):
    id: str
    title: str
    location: str | None = None
    description: str | None = None
    apply_url: str | None = None
    department: str | None = None
    updated_at: str | None = None


def get_path(data, path: str):
    """Resolve 'a.b', 'departments[0].name' style paths. Returns None if absent."""
    current = data
    for part in path.split("."):
        m = _INDEXED.match(part)
        try:
            if m:
                current = current[m.group(1)][int(m.group(2))]
            else:
                current = current[part]
        except (KeyError, IndexError, TypeError):
            return None
    return current


def extract_jobs_array(response_data: dict | list, response_path: str | None) -> list[dict]:
    if response_path is None:
        return response_data if isinstance(response_data, list) else []
    current = get_path(response_data, response_path)
    return current if isinstance(current, list) else []


def map_fields(raw_job: dict, field_mapping: dict) -> MappedJob | None:
    values = {field: get_path(raw_job, path) for field, path in field_mapping.items() if path}
    job_id = values.get("id")
    title = values.get("title")
    if job_id is None or title is None:
        return None
    return MappedJob(
        id=str(job_id),
        title=str(title),
        location=_opt_str(values.get("location")),
        description=_opt_str(values.get("description")),
        apply_url=_opt_str(values.get("apply_url")),
        department=_opt_str(values.get("department")),
        updated_at=_opt_str(values.get("updated_at")),
    )


def _opt_str(value) -> str | None:
    return None if value is None else str(value)
