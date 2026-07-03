import json

from src.ingestion.ingest_eia import build_manifest, row_count, write_local

FAKE_PAGE = {
    "apiVersion": "2.1.6",
    "response": {
        "total": 2,
        "data": [
            {"period": "2024-01-01T00", "respondent": "PJM", "type": "D", "value": 12345},
            {"period": "2024-01-01T01", "respondent": "PJM", "type": "D", "value": 12400},
        ],
    },
}

EMPTY_PAGE = {"apiVersion": "2.1.6", "response": {"total": 0, "data": []}}


def test_row_count_sums_rows_across_pages():
    assert row_count([FAKE_PAGE, FAKE_PAGE]) == 4
    assert row_count([]) == 0


def test_build_manifest_flags_empty_partitions():
    manifest = build_manifest(
        "PJM", "D", "2024-01-01T00", "2024-01-02T00", [EMPTY_PAGE], "2026-07-03"
    )
    assert manifest["row_count"] == 0
    assert manifest["empty"] is True
    assert manifest["region"] == "PJM"
    assert manifest["type"] == "D"


def test_build_manifest_counts_rows_and_pages():
    manifest = build_manifest(
        "PJM", "D", "2024-01-01T00", "2024-01-02T00", [FAKE_PAGE, FAKE_PAGE], "2026-07-03"
    )
    assert manifest["row_count"] == 4
    assert manifest["page_count"] == 2
    assert manifest["empty"] is False
    assert manifest["api_version"] == "2.1.6"


def test_write_local_lands_ndjson_and_manifest(tmp_path):
    manifest = build_manifest(
        "PJM", "D", "2024-01-01T00", "2024-01-02T00", [FAKE_PAGE], "2026-07-03"
    )

    data_path = write_local(
        [FAKE_PAGE], manifest, tmp_path, "gridcast/raw/eia", "PJM", "D", "2026-07-03"
    )

    assert data_path.exists()
    lines = data_path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == FAKE_PAGE

    manifest_path = data_path.parent / "manifest.json"
    assert json.loads(manifest_path.read_text()) == manifest

    expected_dir = tmp_path / "gridcast/raw/eia/region=PJM/type=D/ingest_date=2026-07-03"
    assert data_path.parent == expected_dir
