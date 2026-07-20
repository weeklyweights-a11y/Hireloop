from scripts.generate_company_list import SECTOR, collect_rows, render


def test_sector_is_em_dash():
    assert SECTOR == "—"


def test_render_has_sector_column():
    text = render([("Acme", "greenhouse")])
    assert "| Company | Sector | ATS |" in text
    assert "| Acme | — | greenhouse |" in text


def test_collect_rows_nonempty():
    rows = collect_rows()
    assert len(rows) > 100
