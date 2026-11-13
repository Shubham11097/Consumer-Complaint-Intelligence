import json

from src.ingest_bronze import ingest, sha256_of


def test_files_are_copied_unchanged_with_manifest(tmp_path):
    landing, bronze = tmp_path / "landing", tmp_path / "bronze"
    landing.mkdir(); bronze.mkdir()
    raw = landing / "complaints.csv"
    raw.write_text("Complaint ID,Product\n1,Mortgage\n", encoding="utf-8")

    added = ingest(landing, bronze, "narratives", today="2026-11-06")

    stored = bronze / "narratives" / "2026-11-06" / "complaints.csv"
    assert stored.read_bytes() == raw.read_bytes()
    manifest = json.loads((bronze / "narratives" / "2026-11-06" / "manifest.json").read_text())
    assert manifest["files"][0]["sha256"] == sha256_of(raw)
    assert len(added) == 1


def test_same_file_is_not_ingested_twice(tmp_path):
    landing, bronze = tmp_path / "landing", tmp_path / "bronze"
    landing.mkdir(); bronze.mkdir()
    (landing / "complaints.csv").write_text("Complaint ID\n1\n", encoding="utf-8")

    ingest(landing, bronze, "narratives", today="2026-11-06")
    second = ingest(landing, bronze, "narratives", today="2026-11-07")

    assert second == []
    assert not (bronze / "narratives" / "2026-11-07").exists()


def test_unsupported_files_are_ignored(tmp_path):
    landing, bronze = tmp_path / "landing", tmp_path / "bronze"
    landing.mkdir(); bronze.mkdir()
    (landing / "notes.txt").write_text("not data", encoding="utf-8")

    assert ingest(landing, bronze, "narratives", today="2026-11-06") == []


def test_sources_are_kept_in_separate_folders(tmp_path):
    landing, bronze = tmp_path / "landing", tmp_path / "bronze"
    landing.mkdir(); bronze.mkdir()
    (landing / "live.zip").write_bytes(b"live")
    ingest(landing, bronze, "live", today="2026-11-06")
    (landing / "live.zip").unlink()
    (landing / "2026-08.zip").write_bytes(b"narratives")
    ingest(landing, bronze, "narratives", today="2026-11-06")

    assert (bronze / "live" / "2026-11-06" / "live.zip").exists()
    assert (bronze / "narratives" / "2026-11-06" / "2026-08.zip").exists()
    assert not (bronze / "narratives" / "2026-11-06" / "live.zip").exists()


def test_unknown_source_is_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        ingest(tmp_path, tmp_path, "somewhere", today="2026-11-06")
