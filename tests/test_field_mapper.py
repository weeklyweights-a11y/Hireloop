from src.services.field_mapper import extract_jobs_array, get_path, map_fields

GREENHOUSE_MAPPING = {
    "id": "id",
    "title": "title",
    "location": "location.name",
    "description": "content",
    "apply_url": "absolute_url",
    "department": "departments[0].name",
    "updated_at": "updated_at",
}
LEVER_MAPPING = {
    "id": "id",
    "title": "text",
    "location": "categories.location",
    "description": "descriptionPlain",
    "apply_url": "hostedUrl",
    "department": "categories.department",
    "updated_at": "createdAt",
}


def test_greenhouse_response_mapped():
    raw = {
        "id": 12345,
        "title": "Backend Engineer",
        "location": {"name": "San Francisco, CA"},
        "content": "<p>Great job</p>",
        "absolute_url": "https://boards.greenhouse.io/x/jobs/12345",
        "departments": [{"name": "Engineering"}],
        "updated_at": "2026-07-01T00:00:00Z",
    }
    job = map_fields(raw, GREENHOUSE_MAPPING)
    assert job is not None
    assert job.id == "12345"
    assert job.title == "Backend Engineer"
    assert job.location == "San Francisco, CA"
    assert job.department == "Engineering"


def test_lever_response_mapped():
    raw = {
        "id": "abc-def",
        "text": "Data Scientist",
        "categories": {"location": "New York, NY", "department": "Data"},
        "descriptionPlain": "We are hiring",
        "hostedUrl": "https://jobs.lever.co/x/abc-def",
        "createdAt": 1720000000000,
    }
    job = map_fields(raw, LEVER_MAPPING)
    assert job is not None
    assert job.id == "abc-def"
    assert job.title == "Data Scientist"
    assert job.location == "New York, NY"
    assert job.updated_at == "1720000000000"


def test_nested_path():
    assert get_path({"location": {"name": "SF"}}, "location.name") == "SF"


def test_array_index_path():
    assert get_path({"departments": [{"name": "Eng"}]}, "departments[0].name") == "Eng"


def test_missing_nested_key_returns_none():
    job = map_fields({"id": 1, "title": "X"}, GREENHOUSE_MAPPING)
    assert job is not None
    assert job.location is None
    assert job.department is None


def test_null_value_returns_none():
    job = map_fields({"id": 1, "title": "X", "content": None}, GREENHOUSE_MAPPING)
    assert job is not None
    assert job.description is None


def test_missing_id_or_title_returns_none():
    assert map_fields({"title": "X"}, GREENHOUSE_MAPPING) is None
    assert map_fields({"id": 1}, GREENHOUSE_MAPPING) is None


def test_response_path_extracts_nested_array():
    resp = {"records": {"postings": [{"id": 1}, {"id": 2}]}}
    assert extract_jobs_array(resp, "records.postings") == [{"id": 1}, {"id": 2}]


def test_response_path_none_top_level_array():
    assert extract_jobs_array([{"id": 1}], None) == [{"id": 1}]


def test_empty_response_returns_empty_list():
    assert extract_jobs_array({}, "jobs") == []
    assert extract_jobs_array({}, None) == []
    assert extract_jobs_array({"jobs": "not-a-list"}, "jobs") == []
