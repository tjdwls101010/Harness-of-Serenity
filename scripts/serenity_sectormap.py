#!/usr/bin/env python3
"""Deterministic read-only loader for authored industry sector maps.

Sector maps live at ``sessions/{folder}/_sectormap.json``.  This CLI validates,
shows, filters, and diffs those authored facts; it never scores, ranks, judges, or
executes the evidence pipeline.

	serenity_sectormap.py validate PATH
	serenity_sectormap.py show PATH [--layer ID]
	serenity_sectormap.py layers PATH
	serenity_sectormap.py tickers PATH [--layer ID] [--listing us,adr] [--link CONFIRMED]
	serenity_sectormap.py cohort PATH --layer ID [--include-otc]
	serenity_sectormap.py diff PATH_A PATH_B
	serenity_sectormap.py index

All successful output is deterministic JSON.  Errors are emitted as one-line JSON
envelopes and return a nonzero exit code.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


SCHEMA = "serenity_sectormap/1"
LISTINGS = ("us", "adr", "otc", "foreign")
LINKS = ("CONFIRMED", "DEDUCED")
LIMITATION_CLASSES = ("bottleneck", "constraint", "risk")

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
_SESSIONS = _ROOT / "sessions"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LAYER_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

JsonObject = Dict[str, Any]
Violation = Dict[str, str]

_TOP_LEVEL_FIELDS = {
	"schema",
	"industry",
	"as_of",
	"session",
	"source_notes",
	"layers",
}
_LAYER_FIELDS = {
	"id",
	"name",
	"parent",
	"position",
	"bottleneck_mechanism",
	"limitation_class",
	"concentration",
	"candidates",
	"foreign_only",
	"watch_signal",
}
_CANDIDATE_FIELDS = {"ticker", "role", "listing", "link", "note"}
_FOREIGN_ONLY_FIELDS = {"name", "us_route", "ladder_rung"}


class SectorMapError(Exception):
	"""A user-facing failure that must be serialized as a JSON error envelope."""

	def __init__(self, payload: JsonObject, exit_code: int = 1) -> None:
		super().__init__(str(payload.get("detail", payload.get("error", "sector map error"))))
		self.payload = payload
		self.exit_code = exit_code


class JsonArgumentParser(argparse.ArgumentParser):
	"""Keep argparse failures inside the CLI's JSON-only error contract."""

	def error(self, message: str) -> None:
		raise SectorMapError(
			{"error": "invalid_arguments", "detail": message},
			exit_code=2,
		)


def _emit(value: JsonObject, *, compact: bool = False) -> None:
	if compact:
		json.dump(
			value,
			sys.stdout,
			ensure_ascii=False,
			sort_keys=True,
			separators=(",", ":"),
		)
	else:
		json.dump(value, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
	print()


def _raise_error(error: str, detail: str, **context: Any) -> None:
	raise SectorMapError({"error": error, "detail": detail, **context})


def _add_violation(violations: List[Violation], location: str, detail: str) -> None:
	violations.append({"path": location, "detail": detail})


def _validate_object(
	value: Any,
	location: str,
	fields: Set[str],
	violations: List[Violation],
) -> bool:
	if not isinstance(value, dict):
		_add_violation(violations, location, "expected object")
		return False
	actual = set(value)
	for field in sorted(fields - actual):
		_add_violation(violations, f"{location}.{field}", "missing required field")
	for field in sorted(actual - fields):
		_add_violation(violations, f"{location}.{field}", "unexpected field")
	return True


def _validate_string(
	obj: JsonObject,
	field: str,
	location: str,
	violations: List[Violation],
	*,
	nullable: bool = False,
) -> None:
	if field not in obj:
		return
	value = obj[field]
	if nullable and value is None:
		return
	if not isinstance(value, str):
		expected = "string or null" if nullable else "string"
		_add_violation(violations, f"{location}.{field}", f"expected {expected}")


def _validate_enum(
	obj: JsonObject,
	field: str,
	location: str,
	allowed: Sequence[str],
	violations: List[Violation],
) -> None:
	if field not in obj:
		return
	value = obj[field]
	if not isinstance(value, str) or value not in allowed:
		_add_violation(
			violations,
			f"{location}.{field}",
			f"expected one of {', '.join(allowed)}",
		)


def _validate_candidate(value: Any, location: str, violations: List[Violation]) -> None:
	if not _validate_object(value, location, _CANDIDATE_FIELDS, violations):
		return
	candidate = value
	_validate_string(candidate, "ticker", location, violations)
	_validate_string(candidate, "role", location, violations)
	_validate_enum(candidate, "listing", location, LISTINGS, violations)
	_validate_enum(candidate, "link", location, LINKS, violations)
	_validate_string(candidate, "note", location, violations, nullable=True)


def _validate_foreign_only(value: Any, location: str, violations: List[Violation]) -> None:
	if not _validate_object(value, location, _FOREIGN_ONLY_FIELDS, violations):
		return
	foreign = value
	_validate_string(foreign, "name", location, violations)
	_validate_string(foreign, "us_route", location, violations)
	if "ladder_rung" in foreign:
		rung = foreign["ladder_rung"]
		if type(rung) is not int or rung not in (1, 2, 3, 4):
			_add_violation(
				violations,
				f"{location}.ladder_rung",
				"expected integer 1, 2, 3, or 4",
			)


def _canonical_cycle(nodes: List[str]) -> Tuple[str, ...]:
	rotations = [tuple(nodes[index:] + nodes[:index]) for index in range(len(nodes))]
	return min(rotations)


def _validate_parent_cycles(
	id_locations: Dict[str, List[int]],
	parent_refs: List[Tuple[int, str, str]],
	violations: List[Violation],
) -> None:
	unique_ids = {layer_id for layer_id, indexes in id_locations.items() if len(indexes) == 1}
	graph: Dict[str, str] = {}
	index_by_id = {layer_id: id_locations[layer_id][0] for layer_id in unique_ids}
	for _index, layer_id, parent in parent_refs:
		if layer_id in unique_ids and parent in unique_ids and layer_id != parent:
			graph[layer_id] = parent

	cycles: Set[Tuple[str, ...]] = set()
	for start in sorted(graph):
		seen_at: Dict[str, int] = {}
		path: List[str] = []
		current = start
		while current in graph:
			if current in seen_at:
				cycle = path[seen_at[current]:]
				if cycle:
					cycles.add(_canonical_cycle(cycle))
				break
			seen_at[current] = len(path)
			path.append(current)
			current = graph[current]

	for cycle in sorted(cycles):
		first = cycle[0]
		chain = " -> ".join((*cycle, first))
		_add_violation(
			violations,
			f"$.layers[{index_by_id[first]}].parent",
			f"parent cycle detected: {chain}",
		)


def validate_map(value: Any, source_path: Path) -> List[Violation]:
	"""Return every schema violation in ``value`` without stopping at the first."""
	violations: List[Violation] = []
	if not _validate_object(value, "$", _TOP_LEVEL_FIELDS, violations):
		return violations
	sector_map = value

	if "schema" in sector_map and sector_map["schema"] != SCHEMA:
		_add_violation(
			violations,
			"$.schema",
			f"expected {SCHEMA!r}, got {sector_map['schema']!r}",
		)
	_validate_string(sector_map, "industry", "$", violations)
	_validate_string(sector_map, "session", "$", violations)

	if isinstance(sector_map.get("session"), str):
		expected_session = source_path.parent.name
		if sector_map["session"] != expected_session:
			_add_violation(
				violations,
				"$.session",
				f"expected containing folder name {expected_session!r}",
			)

	if "as_of" in sector_map:
		as_of = sector_map["as_of"]
		valid_date = isinstance(as_of, str) and bool(_DATE_RE.fullmatch(as_of))
		if valid_date:
			try:
				dt.date.fromisoformat(as_of)
			except ValueError:
				valid_date = False
		if not valid_date:
			_add_violation(violations, "$.as_of", "expected a valid date in YYYY-MM-DD format")

	if "source_notes" in sector_map:
		source_notes = sector_map["source_notes"]
		if not isinstance(source_notes, list):
			_add_violation(violations, "$.source_notes", "expected array")
		else:
			for index, note in enumerate(source_notes):
				if not isinstance(note, str):
					_add_violation(
						violations,
						f"$.source_notes[{index}]",
						"expected string",
					)

	id_locations: Dict[str, List[int]] = {}
	parent_refs: List[Tuple[int, str, str]] = []
	layers = sector_map.get("layers")
	if not isinstance(layers, list):
		if "layers" in sector_map:
			_add_violation(violations, "$.layers", "expected array")
		return sorted(violations, key=lambda item: (item["path"], item["detail"]))

	for layer_index, layer_value in enumerate(layers):
		location = f"$.layers[{layer_index}]"
		if not _validate_object(layer_value, location, _LAYER_FIELDS, violations):
			continue
		layer = layer_value
		_validate_string(layer, "id", location, violations)
		_validate_string(layer, "name", location, violations)
		_validate_string(layer, "parent", location, violations, nullable=True)
		_validate_string(layer, "bottleneck_mechanism", location, violations)
		_validate_enum(
			layer,
			"limitation_class",
			location,
			LIMITATION_CLASSES,
			violations,
		)
		_validate_string(layer, "concentration", location, violations)
		_validate_string(layer, "watch_signal", location, violations)

		layer_id = layer.get("id")
		if isinstance(layer_id, str):
			if not _LAYER_ID_RE.fullmatch(layer_id):
				_add_violation(
					violations,
					f"{location}.id",
					"expected unique kebab-case id",
				)
			id_locations.setdefault(layer_id, []).append(layer_index)

		parent = layer.get("parent")
		if isinstance(layer_id, str) and isinstance(parent, str):
			parent_refs.append((layer_index, layer_id, parent))

		if "position" in layer:
			position = layer["position"]
			if type(position) is not int or position < 1:
				_add_violation(
					violations,
					f"{location}.position",
					"expected integer greater than or equal to 1",
				)

		if "candidates" in layer:
			candidates = layer["candidates"]
			if not isinstance(candidates, list):
				_add_violation(violations, f"{location}.candidates", "expected array")
			else:
				for candidate_index, candidate in enumerate(candidates):
					_validate_candidate(
						candidate,
						f"{location}.candidates[{candidate_index}]",
						violations,
					)

		if "foreign_only" in layer:
			foreign_only = layer["foreign_only"]
			if not isinstance(foreign_only, list):
				_add_violation(violations, f"{location}.foreign_only", "expected array")
			else:
				for foreign_index, foreign in enumerate(foreign_only):
					_validate_foreign_only(
						foreign,
						f"{location}.foreign_only[{foreign_index}]",
						violations,
					)

	for layer_id, indexes in sorted(id_locations.items()):
		for duplicate_index in indexes[1:]:
			_add_violation(
				violations,
				f"$.layers[{duplicate_index}].id",
				f"duplicate layer id {layer_id!r}; first declared at $.layers[{indexes[0]}].id",
			)

	all_ids = set(id_locations)
	for layer_index, layer_id, parent in parent_refs:
		if parent == layer_id:
			_add_violation(
				violations,
				f"$.layers[{layer_index}].parent",
				"parent must reference another layer id",
			)
		elif parent not in all_ids:
			_add_violation(
				violations,
				f"$.layers[{layer_index}].parent",
				f"parent references nonexistent layer id {parent!r}",
			)

	_validate_parent_cycles(id_locations, parent_refs, violations)
	return sorted(violations, key=lambda item: (item["path"], item["detail"]))


def load_map(path: Path) -> JsonObject:
	path_text = os.fspath(path)
	try:
		with path.open("r", encoding="utf-8") as handle:
			value = json.load(handle)
	except FileNotFoundError:
		_raise_error(
			"file_not_found",
			f"sector map file not found: {path_text}",
			path=path_text,
		)
	except json.JSONDecodeError as exc:
		_raise_error(
			"malformed_json",
			f"{path_text}: {exc.msg} at line {exc.lineno}, column {exc.colno}",
			path=path_text,
		)
	except UnicodeDecodeError as exc:
		_raise_error(
			"invalid_encoding",
			f"{path_text}: expected UTF-8 JSON ({exc})",
			path=path_text,
		)
	except OSError as exc:
		_raise_error(
			"file_unavailable",
			f"{path_text}: {exc}",
			path=path_text,
		)

	violations = validate_map(value, path)
	if violations:
		raise SectorMapError({
			"error": "validation_failed",
			"detail": f"{len(violations)} schema violation(s) in {path_text}",
			"path": path_text,
			"violations": violations,
		})
	return value


def _find_layer(sector_map: JsonObject, layer_id: str, source_path: Path) -> JsonObject:
	for layer in sector_map["layers"]:
		if layer["id"] == layer_id:
			return layer
	_raise_error(
		"layer_not_found",
		f"layer {layer_id!r} not found in {os.fspath(source_path)}",
		path=os.fspath(source_path),
		layer=layer_id,
	)
	raise AssertionError("unreachable")


def _layer_tickers(layer: JsonObject) -> Set[str]:
	return {candidate["ticker"] for candidate in layer["candidates"]}


def _all_tickers(sector_map: JsonObject) -> Set[str]:
	return {
		candidate["ticker"]
		for layer in sector_map["layers"]
		for candidate in layer["candidates"]
	}


def _parse_listing_filter(raw: Optional[str]) -> Optional[Set[str]]:
	if raw is None:
		return None
	values = [value.strip() for value in raw.split(",") if value.strip()]
	invalid = sorted(set(values) - set(LISTINGS))
	if not values or invalid:
		detail = "expected comma-separated listing values from: " + ", ".join(LISTINGS)
		if invalid:
			detail += f"; invalid: {', '.join(invalid)}"
		_raise_error("invalid_filter", detail, option="--listing")
	return set(values)


def _collect_tickers(
	sector_map: JsonObject,
	*,
	layer_id: Optional[str],
	source_path: Path,
	listings: Optional[Set[str]] = None,
	link: Optional[str] = None,
) -> List[JsonObject]:
	layers = sector_map["layers"]
	if layer_id is not None:
		layers = [_find_layer(sector_map, layer_id, source_path)]

	by_ticker: Dict[str, Set[str]] = {}
	for layer in layers:
		for candidate in layer["candidates"]:
			if listings is not None and candidate["listing"] not in listings:
				continue
			if link is not None and candidate["link"] != link:
				continue
			by_ticker.setdefault(candidate["ticker"], set()).add(layer["id"])

	return [
		{"ticker": ticker, "layers": sorted(by_ticker[ticker])}
		for ticker in sorted(by_ticker)
	]


def cmd_validate(args: argparse.Namespace) -> JsonObject:
	sector_map = load_map(Path(args.path))
	return {
		"ok": True,
		"layers": len(sector_map["layers"]),
		"tickers": len(_all_tickers(sector_map)),
	}


def cmd_show(args: argparse.Namespace) -> JsonObject:
	path = Path(args.path)
	sector_map = load_map(path)
	if args.layer is None:
		return sector_map
	return _find_layer(sector_map, args.layer, path)


def cmd_layers(args: argparse.Namespace) -> JsonObject:
	sector_map = load_map(Path(args.path))
	rows = [
		{
			"id": layer["id"],
			"name": layer["name"],
			"position": layer["position"],
			"limitation_class": layer["limitation_class"],
			"ticker_count": len(_layer_tickers(layer)),
		}
		for layer in sorted(
			sector_map["layers"],
			key=lambda item: (item["position"], item["id"]),
		)
	]
	return {"layers": rows}


def cmd_tickers(args: argparse.Namespace) -> JsonObject:
	path = Path(args.path)
	sector_map = load_map(path)
	listings = _parse_listing_filter(args.listing)
	if args.link is not None and args.link not in LINKS:
		_raise_error(
			"invalid_filter",
			f"expected one of {', '.join(LINKS)}",
			option="--link",
		)
	return {
		"tickers": _collect_tickers(
			sector_map,
			layer_id=args.layer,
			source_path=path,
			listings=listings,
			link=args.link,
		)
	}


def cmd_cohort(args: argparse.Namespace) -> JsonObject:
	path = Path(args.path)
	sector_map = load_map(path)
	listings = {"us", "adr"}
	if args.include_otc:
		listings.add("otc")
	records = _collect_tickers(
		sector_map,
		layer_id=args.layer,
		source_path=path,
		listings=listings,
	)
	tickers = [record["ticker"] for record in records]
	return {
		"layer": args.layer,
		"argv": [
			"scripts/.venv/bin/python",
			"scripts/serenity_pipeline.py",
			"discover",
			*tickers,
		],
	}


def cmd_diff(args: argparse.Namespace) -> JsonObject:
	map_a = load_map(Path(args.path_a))
	map_b = load_map(Path(args.path_b))
	layers_a = {layer["id"]: layer for layer in map_a["layers"]}
	layers_b = {layer["id"]: layer for layer in map_b["layers"]}
	ids_a = set(layers_a)
	ids_b = set(layers_b)

	tickers_added: Dict[str, List[str]] = {}
	tickers_removed: Dict[str, List[str]] = {}
	for layer_id in sorted(ids_a | ids_b):
		a_tickers = _layer_tickers(layers_a[layer_id]) if layer_id in layers_a else set()
		b_tickers = _layer_tickers(layers_b[layer_id]) if layer_id in layers_b else set()
		added = sorted(b_tickers - a_tickers)
		removed = sorted(a_tickers - b_tickers)
		if added:
			tickers_added[layer_id] = added
		if removed:
			tickers_removed[layer_id] = removed

	limitation_changes = [
		{
			"layer": layer_id,
			"from": layers_a[layer_id]["limitation_class"],
			"to": layers_b[layer_id]["limitation_class"],
		}
		for layer_id in sorted(ids_a & ids_b)
		if layers_a[layer_id]["limitation_class"] != layers_b[layer_id]["limitation_class"]
	]
	return {
		"layers_added": sorted(ids_b - ids_a),
		"layers_removed": sorted(ids_a - ids_b),
		"tickers_added": tickers_added,
		"tickers_removed": tickers_removed,
		"limitation_class_changes": limitation_changes,
	}


def cmd_index(_args: argparse.Namespace) -> JsonObject:
	paths = sorted(_SESSIONS.glob("*/_sectormap.json"), key=lambda path: os.fspath(path))
	maps: List[JsonObject] = []
	failures: List[JsonObject] = []
	for path in paths:
		try:
			sector_map = load_map(path)
		except SectorMapError as exc:
			failures.append(exc.payload)
			continue
		maps.append({
			"session": sector_map["session"],
			"industry": sector_map["industry"],
			"as_of": sector_map["as_of"],
			"layers": len(sector_map["layers"]),
		})
	if failures:
		raise SectorMapError({
			"error": "index_failed",
			"detail": f"{len(failures)} invalid sector map(s) under {os.fspath(_SESSIONS)}",
			"path": os.fspath(_SESSIONS),
			"failures": failures,
		})
	maps.sort(key=lambda item: (item["session"], item["as_of"], item["industry"]))
	return {"maps": maps}


def build_parser() -> argparse.ArgumentParser:
	parser = JsonArgumentParser(
		prog="serenity_sectormap.py",
		description="Read-only deterministic loader for authored industry sector maps.",
	)
	sub = parser.add_subparsers(dest="command", required=True)

	sp = sub.add_parser("validate", help="Validate a sector map and report counts")
	sp.add_argument("path", help="Path to _sectormap.json")
	sp.set_defaults(func=cmd_validate)

	sp = sub.add_parser("show", help="Show a whole sector map or one layer")
	sp.add_argument("path", help="Path to _sectormap.json")
	sp.add_argument("--layer", default=None, help="Layer id")
	sp.set_defaults(func=cmd_show)

	sp = sub.add_parser("layers", help="List compact layer metadata")
	sp.add_argument("path", help="Path to _sectormap.json")
	sp.set_defaults(func=cmd_layers)

	sp = sub.add_parser("tickers", help="List deduplicated tickers and their layers")
	sp.add_argument("path", help="Path to _sectormap.json")
	sp.add_argument("--layer", default=None, help="Layer id")
	sp.add_argument("--listing", default=None, help="Comma-separated listing filter, e.g. us,adr")
	sp.add_argument("--link", default=None, help="Link filter: CONFIRMED or DEDUCED")
	sp.set_defaults(func=cmd_tickers)

	sp = sub.add_parser("cohort", help="Build (but do not execute) discover argv for one layer")
	sp.add_argument("path", help="Path to _sectormap.json")
	sp.add_argument("--layer", required=True, help="Layer id")
	sp.add_argument("--include-otc", action="store_true", default=False, help="Include OTC candidates")
	sp.set_defaults(func=cmd_cohort)

	sp = sub.add_parser("diff", help="Diff two validated sector maps")
	sp.add_argument("path_a", help="Earlier _sectormap.json")
	sp.add_argument("path_b", help="Later _sectormap.json")
	sp.set_defaults(func=cmd_diff)

	sp = sub.add_parser("index", help="List all sessions/*/_sectormap.json maps")
	sp.set_defaults(func=cmd_index)
	return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
	try:
		args = build_parser().parse_args(argv)
		result = args.func(args)
	except SectorMapError as exc:
		_emit(exc.payload, compact=True)
		return exc.exit_code
	except Exception as exc:  # noqa: BLE001 — preserve the JSON-only CLI contract
		_emit(
			{
				"error": "internal_error",
				"detail": f"{type(exc).__name__}: {exc}",
			},
			compact=True,
		)
		return 1
	_emit(result)
	return 0


if __name__ == "__main__":
	sys.exit(main())
