from src.routers.jobs import company_jobs, company_insights


def test_company_route_helpers_exist():
    assert callable(company_jobs)
    assert callable(company_insights)
