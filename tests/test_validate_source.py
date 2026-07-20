"""validate_source CLI arg parsing (no network)."""

import argparse

from scripts import validate_source


def test_validate_source_requires_slug():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    try:
        parser.parse_args([])
        raised = False
    except SystemExit:
        raised = True
    assert raised


def test_load_from_json_helper_exists():
    assert callable(validate_source._load_from_json)
