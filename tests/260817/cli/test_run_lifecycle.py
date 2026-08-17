from __future__ import annotations

import json
import hashlib
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
RUN_SCHEMA = json.loads((ROOT / "schemas" / "run-manifest-2.schema.json").read_text(encoding="utf-8"))


def test_start_status_and_abandon_persist_one_typed_run(run_cli, tmp_path: Path) -> None:
    started = run_cli(
        "run",
        "start",
        "--mode",
        "single-name",
        "--question",
        "What would make NVDA investable now?",
        "--subject",
        "NVDA",
        "--as-of",
        "2026-08-17",
    )

    assert started["ok"] is True
    assert started["command"] == "run.start"
    assert started["run"]["schema_id"] == "urn:serenity:schema:run-manifest:2"
    assert started["run"]["status"] == "OPEN"
    assert started["run"]["subjects"] == ["NVDA"]
    run_id = started["run"]["run_id"]

    Draft202012Validator(RUN_SCHEMA).validate(started["run"])
    assert started["run"]["actor"] == {"kind": "model", "id": "harness-agent"}
    assert started["run"]["source_policy"] == {
        "allow_network": True,
        "historical_cutoff": "2026-08-17T23:59:59Z",
        "policy_id": "live-free-v1",
    }
    assert started["run"]["events"][0]["type"] == "run_started"
    unhashed = {key: value for key, value in started["run"].items() if key != "content_hash"}
    expected_hash = hashlib.sha256(
        json.dumps(unhashed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert started["run"]["content_hash"] == expected_hash

    run_file = tmp_path / ".serenity" / "runs" / run_id / "run-manifest.json"
    assert json.loads(run_file.read_text(encoding="utf-8")) == started["run"]

    status = run_cli("run", "status", run_id)
    assert status == {"command": "run.status", "ok": True, "run": started["run"]}

    abandoned = run_cli("run", "abandon", run_id, "--reason", "fixture complete")
    assert abandoned["run"]["status"] == "ABANDONED"
    assert abandoned["run"]["abandon_reason"] == "fixture complete"
    assert abandoned["run"]["updated_at"] >= started["run"]["updated_at"]
    Draft202012Validator(RUN_SCHEMA).validate(abandoned["run"])


def test_invalid_arguments_are_a_single_json_error(run_cli) -> None:
    result = run_cli("run", "start", "--mode", "not-a-mode", expected_exit=2)

    assert result["ok"] is False
    assert result["error"]["code"] == "usage_or_schema"
    assert result["error"]["exit_code"] == 2


def test_single_name_requires_a_subject_before_any_run_is_created(run_cli, tmp_path: Path) -> None:
    result = run_cli(
        "run",
        "start",
        "--mode",
        "single-name",
        "--question",
        "Analyze the unnamed security",
        "--as-of",
        "2026-08-17",
        expected_exit=2,
    )

    assert result["error"]["code"] == "usage_or_schema"
    assert not (tmp_path / ".serenity").exists()


def test_historical_cutoff_must_be_an_iso_datetime(run_cli, tmp_path: Path) -> None:
    result = run_cli(
        "run",
        "start",
        "--mode",
        "macro-event",
        "--question",
        "What was knowable then?",
        "--as-of",
        "2026-08-17",
        "--cutoff",
        "later",
        expected_exit=2,
    )

    assert result["error"]["code"] == "usage_or_schema"
    assert not (tmp_path / ".serenity").exists()


def test_run_start_rejects_a_cutoff_after_its_as_of_day(run_cli, tmp_path: Path) -> None:
    result = run_cli(
        "run",
        "start",
        "--mode",
        "single-name",
        "--question",
        "What was knowable then?",
        "--subject",
        "NVDA",
        "--as-of",
        "2020-01-02",
        "--cutoff",
        "2020-01-03T00:00:00Z",
        expected_exit=2,
    )

    assert result["error"]["code"] == "usage_or_schema"
    assert "as-of" in result["error"]["message"]
    assert not (tmp_path / ".serenity").exists()


def test_status_rejects_a_tampered_manifest_before_returning_it(run_cli, tmp_path: Path) -> None:
    started = run_cli(
        "run",
        "start",
        "--mode",
        "single-name",
        "--question",
        "Check integrity",
        "--subject",
        "NVDA",
        "--as-of",
        "2026-08-17",
    )
    run_id = started["run"]["run_id"]
    path = tmp_path / ".serenity" / "runs" / run_id / "run-manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["question"] = "silently changed"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    result = run_cli("run", "status", run_id, expected_exit=5)

    assert result["error"]["code"] == "persistence_conflict"
    assert "hash" in result["error"]["message"]


def test_status_lists_open_runs_and_close_rejects_an_unfinalized_run(run_cli) -> None:
    started = run_cli(
        "run",
        "start",
        "--mode",
        "macro-event",
        "--question",
        "What changed?",
        "--as-of",
        "2026-08-17",
    )

    status = run_cli("run", "status")
    assert [run["run_id"] for run in status["open_runs"]] == [started["run"]["run_id"]]

    rejected = run_cli("run", "close", started["run"]["run_id"], expected_exit=3)
    assert rejected["error"]["code"] == "invalid_lifecycle"
