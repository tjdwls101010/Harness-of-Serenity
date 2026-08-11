import argparse
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "serenity_sectormap.py"


def _candidate(
	ticker: str,
	*,
	listing: str = "us",
	link: str = "CONFIRMED",
) -> dict[str, Any]:
	return {
		"ticker": ticker,
		"role": f"{ticker} role",
		"listing": listing,
		"link": link,
		"note": None,
	}


def _layer(
	layer_id: str,
	*,
	position: int,
	parent: str | None,
	candidates: list[dict[str, Any]],
) -> dict[str, Any]:
	return {
		"id": layer_id,
		"name": layer_id.replace("-", " ").title(),
		"parent": parent,
		"position": position,
		"bottleneck_mechanism": "Authored mechanism",
		"limitation_class": "bottleneck",
		"concentration": "Authored concentration",
		"candidates": candidates,
		"foreign_only": [
			{
				"name": "비상장 공급사",
				"us_route": "US-listed route",
				"ladder_rung": 2,
			}
		],
		"watch_signal": "Authored watch signal",
	}


def _valid_map(session: str) -> dict[str, Any]:
	return {
		"schema": "serenity_sectormap/1",
		"industry": "Test industry",
		"as_of": "2026-07-26",
		"session": session,
		"source_notes": ["Source A", "출처 B"],
		"layers": [
			_layer(
				"end-demand",
				position=1,
				parent=None,
				candidates=[
					_candidate("NVDA"),
					_candidate("TSM", listing="adr"),
					_candidate("OTCM", listing="otc"),
					_candidate("FOREIGN", listing="foreign", link="DEDUCED"),
				],
			),
			_layer(
				"upstream-input",
				position=2,
				parent="end-demand",
				candidates=[
					_candidate("NVDA", link="DEDUCED"),
					_candidate("ASML", listing="adr"),
				],
			),
		],
	}


def _write_map(
	tmp_path: Path,
	sector_map: Any,
	*,
	folder: str = "260726.test-map",
) -> Path:
	session_dir = tmp_path / folder
	session_dir.mkdir(parents=True, exist_ok=True)
	path = session_dir / "_sectormap.json"
	path.write_text(
		json.dumps(sector_map, ensure_ascii=False),
		encoding="utf-8",
	)
	return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, str(SCRIPT), *args],
		cwd=ROOT,
		capture_output=True,
		text=True,
		check=False,
	)


def _payload(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
	return json.loads(proc.stdout)


def _assert_validation_error(
	proc: subprocess.CompletedProcess[str],
	expected_path: str,
) -> dict[str, Any]:
	assert proc.returncode != 0
	assert proc.stderr == ""
	assert proc.stdout.count("\n") == 1
	payload = _payload(proc)
	assert payload["error"] == "validation_failed"
	assert expected_path in {item["path"] for item in payload["violations"]}
	return payload


def test_valid_load_and_read_commands_are_deterministic(tmp_path: Path) -> None:
	folder = "260726.test-map"
	path = _write_map(tmp_path, _valid_map(folder), folder=folder)

	validate = _run("validate", str(path))
	assert validate.returncode == 0
	assert _payload(validate) == {"ok": True, "layers": 2, "tickers": 5}

	show = _run("show", str(path))
	assert show.returncode == 0
	assert _payload(show) == _valid_map(folder)
	assert _run("show", str(path)).stdout == show.stdout

	show_layer = _run("show", str(path), "--layer", "upstream-input")
	assert show_layer.returncode == 0
	assert _payload(show_layer)["id"] == "upstream-input"

	layers = _run("layers", str(path))
	assert _payload(layers) == {
		"layers": [
			{
				"id": "end-demand",
				"name": "End Demand",
				"position": 1,
				"limitation_class": "bottleneck",
				"ticker_count": 4,
			},
			{
				"id": "upstream-input",
				"name": "Upstream Input",
				"position": 2,
				"limitation_class": "bottleneck",
				"ticker_count": 2,
			},
		]
	}


def test_tickers_are_filtered_deduplicated_and_sorted(tmp_path: Path) -> None:
	folder = "260726.ticker-map"
	path = _write_map(tmp_path, _valid_map(folder), folder=folder)

	all_tickers = _run("tickers", str(path))
	assert _payload(all_tickers) == {
		"tickers": [
			{"ticker": "ASML", "layers": ["upstream-input"]},
			{"ticker": "FOREIGN", "layers": ["end-demand"]},
			{"ticker": "NVDA", "layers": ["end-demand", "upstream-input"]},
			{"ticker": "OTCM", "layers": ["end-demand"]},
			{"ticker": "TSM", "layers": ["end-demand"]},
		]
	}

	filtered = _run(
		"tickers",
		str(path),
		"--listing",
		"us,adr",
		"--link",
		"CONFIRMED",
	)
	assert _payload(filtered) == {
		"tickers": [
			{"ticker": "ASML", "layers": ["upstream-input"]},
			{"ticker": "NVDA", "layers": ["end-demand"]},
			{"ticker": "TSM", "layers": ["end-demand"]},
		]
	}

	one_layer = _run("tickers", str(path), "--layer", "upstream-input")
	assert _payload(one_layer) == {
		"tickers": [
			{"ticker": "ASML", "layers": ["upstream-input"]},
			{"ticker": "NVDA", "layers": ["upstream-input"]},
		]
	}


def test_missing_malformed_and_wrong_schema_are_clean_errors(tmp_path: Path) -> None:
	missing = tmp_path / "missing" / "_sectormap.json"
	missing_proc = _run("validate", str(missing))
	assert missing_proc.returncode != 0
	assert missing_proc.stderr == ""
	assert missing_proc.stdout.count("\n") == 1
	assert _payload(missing_proc)["error"] == "file_not_found"
	assert _payload(missing_proc)["path"] == str(missing)

	malformed_dir = tmp_path / "260726.malformed"
	malformed_dir.mkdir()
	malformed = malformed_dir / "_sectormap.json"
	malformed.write_text('{"schema": ', encoding="utf-8")
	malformed_proc = _run("validate", str(malformed))
	assert malformed_proc.returncode != 0
	assert malformed_proc.stderr == ""
	assert malformed_proc.stdout.count("\n") == 1
	assert _payload(malformed_proc)["error"] == "malformed_json"
	assert _payload(malformed_proc)["path"] == str(malformed)

	folder = "260726.wrong-schema"
	wrong = _valid_map(folder)
	wrong["schema"] = "serenity_sectormap/999"
	wrong_path = _write_map(tmp_path, wrong, folder=folder)
	payload = _assert_validation_error(
		_run("validate", str(wrong_path)),
		"$.schema",
	)
	assert "serenity_sectormap/1" in payload["violations"][0]["detail"]


VALIDATION_CASES = (
	("root-not-object", "$"),
	("missing-top-field", "$.industry"),
	("unexpected-top-field", "$.extra"),
	("industry-type", "$.industry"),
	("as-of-invalid", "$.as_of"),
	("session-type", "$.session"),
	("session-folder-mismatch", "$.session"),
	("source-notes-type", "$.source_notes"),
	("source-note-type", "$.source_notes[0]"),
	("layers-type", "$.layers"),
	("layer-not-object", "$.layers[0]"),
	("missing-layer-field", "$.layers[0].watch_signal"),
	("unexpected-layer-field", "$.layers[0].extra"),
	("layer-id-type", "$.layers[0].id"),
	("layer-id-not-kebab", "$.layers[0].id"),
	("layer-name-type", "$.layers[0].name"),
	("parent-type", "$.layers[0].parent"),
	("position-type", "$.layers[0].position"),
	("position-bool", "$.layers[0].position"),
	("position-range", "$.layers[0].position"),
	("mechanism-type", "$.layers[0].bottleneck_mechanism"),
	("limitation-class", "$.layers[0].limitation_class"),
	("concentration-type", "$.layers[0].concentration"),
	("candidates-type", "$.layers[0].candidates"),
	("foreign-only-type", "$.layers[0].foreign_only"),
	("watch-signal-type", "$.layers[0].watch_signal"),
	("candidate-not-object", "$.layers[0].candidates[0]"),
	("missing-candidate-field", "$.layers[0].candidates[0].ticker"),
	("unexpected-candidate-field", "$.layers[0].candidates[0].extra"),
	("ticker-type", "$.layers[0].candidates[0].ticker"),
	("role-type", "$.layers[0].candidates[0].role"),
	("listing-value", "$.layers[0].candidates[0].listing"),
	("link-value", "$.layers[0].candidates[0].link"),
	("note-type", "$.layers[0].candidates[0].note"),
	("foreign-not-object", "$.layers[0].foreign_only[0]"),
	("missing-foreign-field", "$.layers[0].foreign_only[0].name"),
	("unexpected-foreign-field", "$.layers[0].foreign_only[0].extra"),
	("foreign-name-type", "$.layers[0].foreign_only[0].name"),
	("us-route-type", "$.layers[0].foreign_only[0].us_route"),
	("ladder-rung-type", "$.layers[0].foreign_only[0].ladder_rung"),
	("ladder-rung-value", "$.layers[0].foreign_only[0].ladder_rung"),
)


def _invalid_payload(case: str, session: str) -> Any:
	data = _valid_map(session)
	if case == "root-not-object":
		return []
	if case == "missing-top-field":
		del data["industry"]
	elif case == "unexpected-top-field":
		data["extra"] = True
	elif case == "industry-type":
		data["industry"] = 42
	elif case == "as-of-invalid":
		data["as_of"] = "2026-02-30"
	elif case == "session-type":
		data["session"] = 42
	elif case == "session-folder-mismatch":
		data["session"] = "different-folder"
	elif case == "source-notes-type":
		data["source_notes"] = "not-an-array"
	elif case == "source-note-type":
		data["source_notes"][0] = 42
	elif case == "layers-type":
		data["layers"] = "not-an-array"
	elif case == "layer-not-object":
		data["layers"][0] = []
	elif case == "missing-layer-field":
		del data["layers"][0]["watch_signal"]
	elif case == "unexpected-layer-field":
		data["layers"][0]["extra"] = True
	elif case == "layer-id-type":
		data["layers"][0]["id"] = 42
	elif case == "layer-id-not-kebab":
		data["layers"][0]["id"] = "Not_Kebab"
	elif case == "layer-name-type":
		data["layers"][0]["name"] = 42
	elif case == "parent-type":
		data["layers"][0]["parent"] = 42
	elif case == "position-type":
		data["layers"][0]["position"] = "1"
	elif case == "position-bool":
		data["layers"][0]["position"] = True
	elif case == "position-range":
		data["layers"][0]["position"] = 0
	elif case == "mechanism-type":
		data["layers"][0]["bottleneck_mechanism"] = 42
	elif case == "limitation-class":
		data["layers"][0]["limitation_class"] = "verdict"
	elif case == "concentration-type":
		data["layers"][0]["concentration"] = 42
	elif case == "candidates-type":
		data["layers"][0]["candidates"] = "not-an-array"
	elif case == "foreign-only-type":
		data["layers"][0]["foreign_only"] = "not-an-array"
	elif case == "watch-signal-type":
		data["layers"][0]["watch_signal"] = 42
	elif case == "candidate-not-object":
		data["layers"][0]["candidates"][0] = []
	elif case == "missing-candidate-field":
		del data["layers"][0]["candidates"][0]["ticker"]
	elif case == "unexpected-candidate-field":
		data["layers"][0]["candidates"][0]["extra"] = True
	elif case == "ticker-type":
		data["layers"][0]["candidates"][0]["ticker"] = 42
	elif case == "role-type":
		data["layers"][0]["candidates"][0]["role"] = 42
	elif case == "listing-value":
		data["layers"][0]["candidates"][0]["listing"] = "pink"
	elif case == "link-value":
		data["layers"][0]["candidates"][0]["link"] = "MAYBE"
	elif case == "note-type":
		data["layers"][0]["candidates"][0]["note"] = 42
	elif case == "foreign-not-object":
		data["layers"][0]["foreign_only"][0] = []
	elif case == "missing-foreign-field":
		del data["layers"][0]["foreign_only"][0]["name"]
	elif case == "unexpected-foreign-field":
		data["layers"][0]["foreign_only"][0]["extra"] = True
	elif case == "foreign-name-type":
		data["layers"][0]["foreign_only"][0]["name"] = 42
	elif case == "us-route-type":
		data["layers"][0]["foreign_only"][0]["us_route"] = 42
	elif case == "ladder-rung-type":
		data["layers"][0]["foreign_only"][0]["ladder_rung"] = True
	elif case == "ladder-rung-value":
		data["layers"][0]["foreign_only"][0]["ladder_rung"] = 5
	else:
		raise AssertionError(f"unknown validation case: {case}")
	return data


@pytest.mark.parametrize(("case", "expected_path"), VALIDATION_CASES)
def test_every_schema_validation_mode(
	tmp_path: Path,
	case: str,
	expected_path: str,
) -> None:
	folder = f"260726.{case}"
	path = _write_map(
		tmp_path,
		_invalid_payload(case, folder),
		folder=folder,
	)
	_assert_validation_error(_run("validate", str(path)), expected_path)


def test_validation_reports_every_violation_in_deterministic_order(tmp_path: Path) -> None:
	folder = "260726.many-errors"
	data = _valid_map(folder)
	data["schema"] = "wrong"
	data["as_of"] = "not-a-date"
	data["source_notes"] = [42]
	data["layers"][0]["limitation_class"] = "unknown"
	data["layers"][0]["candidates"][0]["listing"] = "unknown"
	path = _write_map(tmp_path, data, folder=folder)

	payload = _assert_validation_error(_run("validate", str(path)), "$.schema")
	paths = [item["path"] for item in payload["violations"]]
	assert paths == sorted(paths)
	assert set(paths) == {
		"$.as_of",
		"$.layers[0].candidates[0].listing",
		"$.layers[0].limitation_class",
		"$.schema",
		"$.source_notes[0]",
	}
	assert payload["detail"].startswith("5 schema violation(s)")


def test_duplicate_layer_ids_are_rejected(tmp_path: Path) -> None:
	folder = "260726.duplicate"
	data = _valid_map(folder)
	data["layers"][1]["id"] = data["layers"][0]["id"]
	data["layers"][1]["parent"] = None
	path = _write_map(tmp_path, data, folder=folder)

	payload = _assert_validation_error(
		_run("validate", str(path)),
		"$.layers[1].id",
	)
	assert any(
		"duplicate layer id" in item["detail"]
		for item in payload["violations"]
	)


def test_parent_pointing_at_nonexistent_layer_is_rejected(tmp_path: Path) -> None:
	folder = "260726.bad-parent"
	data = _valid_map(folder)
	data["layers"][1]["parent"] = "missing-layer"
	path = _write_map(tmp_path, data, folder=folder)

	payload = _assert_validation_error(
		_run("validate", str(path)),
		"$.layers[1].parent",
	)
	assert any(
		"nonexistent layer id" in item["detail"]
		for item in payload["violations"]
	)


@pytest.mark.parametrize("mode", ("self", "cycle"))
def test_invalid_parent_nesting_is_rejected(tmp_path: Path, mode: str) -> None:
	folder = f"260726.parent-{mode}"
	data = _valid_map(folder)
	if mode == "self":
		data["layers"][0]["parent"] = "end-demand"
	else:
		data["layers"][0]["parent"] = "upstream-input"
	path = _write_map(tmp_path, data, folder=folder)

	payload = _assert_validation_error(
		_run("validate", str(path)),
		"$.layers[0].parent",
	)
	expected = "another layer" if mode == "self" else "cycle"
	assert any(expected in item["detail"] for item in payload["violations"])


def test_cohort_argv_generation_and_otc_opt_in(tmp_path: Path) -> None:
	folder = "260726.cohort"
	path = _write_map(tmp_path, _valid_map(folder), folder=folder)

	default = _run("cohort", str(path), "--layer", "end-demand")
	assert default.returncode == 0
	assert _payload(default) == {
		"layer": "end-demand",
		"argv": [
			"scripts/.venv/bin/python",
			"scripts/serenity_pipeline.py",
			"discover",
			"NVDA",
			"TSM",
		],
	}

	with_otc = _run(
		"cohort",
		str(path),
		"--layer",
		"end-demand",
		"--include-otc",
	)
	assert with_otc.returncode == 0
	assert _payload(with_otc) == {
		"layer": "end-demand",
		"argv": [
			"scripts/.venv/bin/python",
			"scripts/serenity_pipeline.py",
			"discover",
			"NVDA",
			"OTCM",
			"TSM",
		],
	}


def test_diff_output(tmp_path: Path) -> None:
	folder_a = "260725.diff-a"
	folder_b = "260726.diff-b"
	map_a = _valid_map(folder_a)
	map_b = _valid_map(folder_b)
	map_b["layers"][0]["limitation_class"] = "constraint"
	map_b["layers"][0]["candidates"] = [
		candidate
		for candidate in map_b["layers"][0]["candidates"]
		if candidate["ticker"] != "TSM"
	]
	map_b["layers"][0]["candidates"].append(_candidate("AMD"))
	map_b["layers"] = [
		map_b["layers"][0],
		_layer(
			"packaging",
			position=2,
			parent="end-demand",
			candidates=[_candidate("ASML", listing="adr")],
		),
	]
	path_a = _write_map(tmp_path, map_a, folder=folder_a)
	path_b = _write_map(tmp_path, map_b, folder=folder_b)

	proc = _run("diff", str(path_a), str(path_b))
	assert proc.returncode == 0
	assert _payload(proc) == {
		"layers_added": ["packaging"],
		"layers_removed": ["upstream-input"],
		"tickers_added": {
			"end-demand": ["AMD"],
			"packaging": ["ASML"],
		},
		"tickers_removed": {
			"end-demand": ["TSM"],
			"upstream-input": ["ASML", "NVDA"],
		},
		"limitation_class_changes": [
			{
				"layer": "end-demand",
				"from": "bottleneck",
				"to": "constraint",
			}
		],
	}


def test_unicode_path_and_content(tmp_path: Path) -> None:
	folder = "260726. 반도체 공급망 지도"
	data = _valid_map(folder)
	data["industry"] = "반도체 및 첨단 패키징"
	path = _write_map(tmp_path, data, folder=folder)

	validate = _run("validate", str(path))
	assert validate.returncode == 0
	assert _payload(validate)["ok"] is True

	show = _run("show", str(path))
	assert show.returncode == 0
	assert _payload(show)["industry"] == "반도체 및 첨단 패키징"
	assert "반도체 및 첨단 패키징" in show.stdout


def test_layer_and_filter_errors_are_json_envelopes(tmp_path: Path) -> None:
	folder = "260726.command-errors"
	path = _write_map(tmp_path, _valid_map(folder), folder=folder)

	missing_layer = _run("show", str(path), "--layer", "missing")
	assert missing_layer.returncode != 0
	assert missing_layer.stderr == ""
	assert _payload(missing_layer)["error"] == "layer_not_found"

	bad_listing = _run("tickers", str(path), "--listing", "us,pink")
	assert bad_listing.returncode != 0
	assert bad_listing.stderr == ""
	assert _payload(bad_listing)["error"] == "invalid_filter"

	bad_link = _run("tickers", str(path), "--link", "MAYBE")
	assert bad_link.returncode != 0
	assert bad_link.stderr == ""
	assert _payload(bad_link)["error"] == "invalid_filter"


def test_index_lists_valid_maps_in_deterministic_order(
	tmp_path: Path,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	spec = importlib.util.spec_from_file_location("serenity_sectormap_test", SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)

	sessions = tmp_path / "sessions"
	first_folder = "260725. 첫 지도"
	second_folder = "260726.second-map"
	_write_map(sessions, _valid_map(second_folder), folder=second_folder)
	first = _valid_map(first_folder)
	first["industry"] = "첫 산업"
	_write_map(sessions, first, folder=first_folder)
	monkeypatch.setattr(module, "_SESSIONS", sessions)

	result = module.cmd_index(argparse.Namespace())
	assert result == {
		"maps": [
			{
				"session": first_folder,
				"industry": "첫 산업",
				"as_of": "2026-07-26",
				"layers": 2,
			},
			{
				"session": second_folder,
				"industry": "Test industry",
				"as_of": "2026-07-26",
				"layers": 2,
			},
		]
	}


def test_show_does_not_mutate_loaded_data(tmp_path: Path) -> None:
	folder = "260726.read-only"
	data = _valid_map(folder)
	expected = copy.deepcopy(data)
	path = _write_map(tmp_path, data, folder=folder)

	_run("show", str(path), "--layer", "end-demand")
	assert json.loads(path.read_text(encoding="utf-8")) == expected
