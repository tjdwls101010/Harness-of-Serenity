import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS_DIR.parents[3]
FIXTURE = SCRIPTS_DIR / "tests" / "golden" / "AAOI.inputs.json"
FORBIDDEN_KEYS = {
	"objective_screen",
	"screen_score",
	"priced_in_assessment",
	"risk_score",
	"flow_assessment",
	"vehicle_menu",
	"verdict",
	"rating",
	"recommendation",
	"signals",
	"assessment",
}
FORBIDDEN_VALUES = {"BUY", "SELL", "STRONG_BUY", "MOONSHOT", "ACCUMULATE", "AVOID"}
FORBIDDEN_VALUE_TOKENS = ("buy", "sell", "strong_buy", "strong buy", "accumulate", "avoid", "moonshot")
FORBIDDEN_KEY_NORMALIZED = {
	"".join(ch for ch in key.lower() if ch.isalnum())
	for key in FORBIDDEN_KEYS
}


def _walk_keys(value: object) -> Iterable[str]:
	if isinstance(value, dict):
		for key, child in value.items():
			yield str(key)
			yield from _walk_keys(child)
	elif isinstance(value, list):
		for child in value:
			yield from _walk_keys(child)


def _walk_strings(value: object) -> Iterable[str]:
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for child in value.values():
			yield from _walk_strings(child)
	elif isinstance(value, list):
		for child in value:
			yield from _walk_strings(child)


def test_pipeline_evidence_command_is_judgment_free() -> None:
	proc = subprocess.run(
		[
			sys.executable,
			str(ROOT / "scripts" / "serenity_pipeline.py"),
			"evidence",
			"--fixture",
			str(FIXTURE),
			"--json",
		],
		cwd=ROOT,
		capture_output=True,
		text=True,
		check=True,
	)
	payload = json.loads(proc.stdout)

	assert payload["evidence_contract"]["judgment_owner"] == "agent"
	assert payload["evidence_contract"]["code_role"] == "load_and_normalize_evidence"
	assert payload["ticker"] == "AAOI"
	assert "key_facts" in payload
	assert "filing_evidence" in payload

	all_keys = set(_walk_keys(payload))
	assert not (all_keys & FORBIDDEN_KEYS)
	assert not [
		key for key in all_keys
		if "".join(ch for ch in key.lower() if ch.isalnum()) in FORBIDDEN_KEY_NORMALIZED
	]
	all_values = {value.strip() for value in _walk_strings(payload)}
	assert not (all_values & FORBIDDEN_VALUES)
	assert not [
		value for value in all_values
		if any(token in value.lower() for token in FORBIDDEN_VALUE_TOKENS)
	]


def test_pipeline_evidence_sanitizes_non_null_macro_payload(tmp_path: Path) -> None:
	fixture = tmp_path / "TEST.inputs.json"
	fixture.write_text(
		json.dumps(
			{
				"l1": {
					"verdict": "BUY",
					"Verdict": "neutral-looking but forbidden key",
					"risk_score": 12,
					"Risk_Score": 13,
					"Recommendation": "hold",
					"signals": {"vix": 20},
					"label_one": "Buy",
					"label_two": "strong buy",
					"label_three": "strong_buy",
					"label_four": "please sell",
					"raw_inputs": {"vix_spot": 20, "dxy": 105},
				},
				"l4": {},
				"l5": {},
				"sec_sc": {},
			}
		),
		encoding="utf-8",
	)
	proc = subprocess.run(
		[
			sys.executable,
			str(ROOT / "scripts" / "serenity_pipeline.py"),
			"evidence",
			"--fixture",
			str(fixture),
			"--json",
		],
		cwd=ROOT,
		capture_output=True,
		text=True,
		check=True,
	)
	payload = json.loads(proc.stdout)

	all_keys = set(_walk_keys(payload))
	all_values = {value.strip() for value in _walk_strings(payload)}
	assert not (all_keys & FORBIDDEN_KEYS)
	assert not [
		key for key in all_keys
		if "".join(ch for ch in key.lower() if ch.isalnum()) in FORBIDDEN_KEY_NORMALIZED
	]
	assert "signals" not in all_keys
	assert "assessment" not in all_keys
	assert not (all_values & FORBIDDEN_VALUES)
	assert not [
		value for value in all_values
		if any(token in value.lower() for token in FORBIDDEN_VALUE_TOKENS)
	]
	assert payload["macro_inputs"] == {"raw_inputs": {"vix_spot": 20, "dxy": 105}}
