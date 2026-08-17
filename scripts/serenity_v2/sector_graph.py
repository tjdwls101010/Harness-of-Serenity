"""Structural validation for a supply-chain sector graph.

This module deliberately validates evidence, chain shape, and vehicle resolution only. It does
not infer whether a node is a bottleneck or decide which security is a better investment.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from serenity_v2.runtime import canonical_hash
from serenity_v2.schema import SchemaViolation, validate_document


SCHEMA_ID = "urn:serenity:schema:sector-graph:1"
RUN_MANIFEST_SCHEMA_ID = "urn:serenity:schema:run-manifest:2"
EVIDENCE_RESULT_SCHEMA_ID = "urn:serenity:schema:evidence-result:1"
NODE_TYPES = frozenset({"industry", "layer", "company", "asset", "input", "jurisdiction", "standard"})
EDGE_TYPES = frozenset({"depends_on", "supplies", "qualifies", "finances", "controls_capacity", "substitutes"})
BOTTLENECK_RELATIONSHIPS = frozenset({"owns", "supplies", "enables"})
VEHICLE_RESOLUTIONS = frozenset({"clean_vehicle", "indirect_vehicle", "no_clean_vehicle"})
CONCENTRATION_VECTORS = frozenset({"tightening", "stable", "loosening", "unknown"})
EXPOSURE_CLASSES = frozenset({"owner", "partial_owner", "supplier_to_owner", "theme_proxy"})
REVENUE_LINK_STATUSES = frozenset({"disclosed", "deduced", "unresolved"})
EXPRESSION_ROLES = frozenset({"primary", "secondary"})


class SectorGraphValidationError(ValueError):
    """Raised when a graph cannot support a traceable supply-chain claim."""


def build_sector_graph(
    graph: Mapping[str, Any],
    *,
    run_manifest: Mapping[str, Any],
    evidence_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return an independently owned graph bound to hash-valid saved evidence results."""

    return validate_sector_graph(
        deepcopy(dict(graph)),
        run_manifest=run_manifest,
        evidence_results=evidence_results,
    )


def validate_sector_graph(
    graph: Mapping[str, Any],
    *,
    run_manifest: Mapping[str, Any],
    evidence_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the graph and bind each evidence reference to a saved run artifact."""

    document = _mapping(graph, "graph")
    _required_string(document, "schema_id", "graph")
    if document["schema_id"] != SCHEMA_ID:
        _fail("graph.schema_id must be urn:serenity:schema:sector-graph:1")
    for field in ("graph_id", "run_id", "as_of"):
        _required_string(document, field, "graph")

    evidence_ids = _id_set(document.get("evidence_refs"), "graph.evidence_refs")
    node_index = _validate_nodes(document.get("nodes"), evidence_ids)
    edges = _validate_edges(document.get("edges"), node_index, evidence_ids)

    headline_node_id = _required_string(document, "headline_node_id", "graph")
    _require_node(headline_node_id, node_index, "graph.headline_node_id")
    bottleneck_node_ids = _id_list(document.get("bottleneck_node_ids"), "graph.bottleneck_node_ids", minimum=1)
    if headline_node_id not in bottleneck_node_ids:
        _fail("graph.headline_node_id must be included in graph.bottleneck_node_ids")
    for node_id in bottleneck_node_ids:
        node = _require_node(node_id, node_index, "graph.bottleneck_node_ids")
        if node["relationship_to_bottleneck"] == "theme_exposure":
            _fail(f"theme exposure node cannot be asserted as bottleneck ownership: {node_id}")
        if node["relationship_to_bottleneck"] not in BOTTLENECK_RELATIONSHIPS:
            _fail(f"bottleneck node requires a structural relationship: {node_id}")

    _validate_dependency_dag(edges)
    _validate_recursive_bottom_hop(document.get("recursive_bottom_hop"), headline_node_id, node_index, edges, evidence_ids)
    _validate_sibling_comparison(document.get("sibling_comparison"), node_index, evidence_ids)
    _validate_second_order_effect(document.get("second_order_effect"), node_index, evidence_ids)
    _validate_ownership_concentration(document.get("ownership_concentration"), node_index, evidence_ids)
    _validate_us_expression(document.get("us_expression"), node_index, evidence_ids)
    _validate_saved_evidence_context(
        document,
        evidence_ids,
        run_manifest=run_manifest,
        evidence_results=evidence_results,
    )

    return deepcopy(document)


def _validate_saved_evidence_context(
    graph: Mapping[str, Any],
    evidence_ids: set[str],
    *,
    run_manifest: Mapping[str, Any],
    evidence_results: Sequence[Mapping[str, Any]],
) -> None:
    manifest = _mapping(run_manifest, "run_manifest")
    _validate_saved_document(manifest, RUN_MANIFEST_SCHEMA_ID, "run manifest")
    manifest_run_id = _required_string(manifest, "run_id", "run_manifest")
    if graph["run_id"] != manifest_run_id:
        _fail("graph.run_id does not match the saved run manifest")
    if graph["as_of"] != manifest.get("as_of"):
        _fail("graph.as_of does not match the saved run manifest")

    results = _sequence(evidence_results, "evidence_results", minimum=0)
    result_ids: set[str] = set()
    for position, raw_result in enumerate(results):
        path = f"evidence_results[{position}]"
        result = _mapping(raw_result, path)
        _validate_saved_document(result, EVIDENCE_RESULT_SCHEMA_ID, "saved evidence result")
        result_id = _required_string(result, "result_id", path)
        if result_id in result_ids:
            _fail(f"duplicate saved evidence result: {result_id}")
        if result["run_id"] != manifest_run_id:
            _fail(f"saved evidence result does not match the run manifest: {result_id}")
        result_ids.add(result_id)

    missing = sorted(evidence_ids - result_ids)
    if missing:
        _fail(f"graph evidence reference has no saved evidence result: {', '.join(missing)}")


def _validate_saved_document(document: Mapping[str, Any], schema_id: str, label: str) -> None:
    try:
        validate_document(dict(document), schema_id)
    except SchemaViolation as exc:
        _fail(f"{label} is not schema-valid: {exc}")
    expected_hash = canonical_hash({key: value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected_hash:
        _fail(f"{label} content_hash does not match canonical content")


def _validate_nodes(value: Any, evidence_ids: set[str]) -> dict[str, dict[str, Any]]:
    nodes = _sequence(value, "graph.nodes", minimum=1)
    index: dict[str, dict[str, Any]] = {}
    for position, raw_node in enumerate(nodes):
        path = f"graph.nodes[{position}]"
        node = _mapping(raw_node, path)
        node_id = _required_string(node, "node_id", path)
        if node_id in index:
            _fail(f"duplicate node_id: {node_id}")
        node_type = _required_string(node, "node_type", path)
        if node_type not in NODE_TYPES:
            _fail(f"{path}.node_type must be one of {sorted(NODE_TYPES)}")
        _required_string(node, "label", path)
        relationship = _required_string(node, "relationship_to_bottleneck", path)
        if relationship not in {*BOTTLENECK_RELATIONSHIPS, "theme_exposure", "not_assessed"}:
            _fail(f"{path}.relationship_to_bottleneck is invalid")
        _validate_claims(node.get("claims"), f"{path}.claims", evidence_ids)
        index[node_id] = node
    return index


def _validate_edges(value: Any, node_index: Mapping[str, dict[str, Any]], evidence_ids: set[str]) -> list[dict[str, Any]]:
    edges = _sequence(value, "graph.edges", minimum=1)
    validated: list[dict[str, Any]] = []
    for position, raw_edge in enumerate(edges):
        path = f"graph.edges[{position}]"
        edge = _mapping(raw_edge, path)
        from_node_id = _required_string(edge, "from_node_id", path)
        to_node_id = _required_string(edge, "to_node_id", path)
        _require_node(from_node_id, node_index, f"{path}.from_node_id")
        _require_node(to_node_id, node_index, f"{path}.to_node_id")
        edge_type = _required_string(edge, "edge_type", path)
        if edge_type not in EDGE_TYPES:
            _fail(f"{path}.edge_type must be one of {sorted(EDGE_TYPES)}")
        _validate_claims(edge.get("claims"), f"{path}.claims", evidence_ids)
        validated.append(edge)
    return validated


def _validate_dependency_dag(edges: Sequence[dict[str, Any]]) -> None:
    dependencies: dict[str, set[str]] = {}
    for edge in edges:
        if edge["edge_type"] == "depends_on":
            dependencies.setdefault(edge["from_node_id"], set()).add(edge["to_node_id"])

    active: set[str] = set()
    completed: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in active:
            _fail("dependency graph contains a cycle")
        if node_id in completed:
            return
        active.add(node_id)
        for next_node_id in dependencies.get(node_id, ()):
            visit(next_node_id)
        active.remove(node_id)
        completed.add(node_id)

    for node_id in dependencies:
        visit(node_id)


def _validate_recursive_bottom_hop(
    value: Any,
    headline_node_id: str,
    node_index: Mapping[str, dict[str, Any]],
    edges: Sequence[dict[str, Any]],
    evidence_ids: set[str],
) -> None:
    bottom_hop = _mapping(value, "graph.recursive_bottom_hop")
    bottom_node_id = _required_string(bottom_hop, "node_id", "graph.recursive_bottom_hop")
    _require_node(bottom_node_id, node_index, "graph.recursive_bottom_hop.node_id")
    if bottom_node_id == headline_node_id:
        _fail("recursive bottom hop must be distinct from the headline node")
    path = _id_list(bottom_hop.get("path"), "graph.recursive_bottom_hop.path", minimum=2)
    if path[0] != headline_node_id or path[-1] != bottom_node_id:
        _fail("recursive bottom hop path must begin at the headline node and end at the bottom hop")
    for node_id in path:
        _require_node(node_id, node_index, "graph.recursive_bottom_hop.path")
    dependency_pairs = {(edge["from_node_id"], edge["to_node_id"]) for edge in edges if edge["edge_type"] == "depends_on"}
    if any((left, right) not in dependency_pairs for left, right in zip(path, path[1:])):
        _fail("recursive bottom hop path must run through depends_on edges")
    stop_rationale = _mapping(bottom_hop.get("stop_rationale"), "graph.recursive_bottom_hop.stop_rationale")
    _required_string(stop_rationale, "reason", "graph.recursive_bottom_hop.stop_rationale")
    _validate_evidence_refs(stop_rationale.get("evidence_refs"), "graph.recursive_bottom_hop.stop_rationale.evidence_refs", evidence_ids)


def _validate_sibling_comparison(value: Any, node_index: Mapping[str, dict[str, Any]], evidence_ids: set[str]) -> None:
    comparison = _mapping(value, "graph.sibling_comparison")
    node_ids = _id_list(comparison.get("node_ids"), "graph.sibling_comparison.node_ids", minimum=2)
    if len(set(node_ids)) != len(node_ids):
        _fail("graph.sibling_comparison.node_ids must be distinct")
    for node_id in node_ids:
        _require_node(node_id, node_index, "graph.sibling_comparison.node_ids")
    _required_string(comparison, "statement", "graph.sibling_comparison")
    _validate_evidence_refs(comparison.get("evidence_refs"), "graph.sibling_comparison.evidence_refs", evidence_ids)


def _validate_second_order_effect(value: Any, node_index: Mapping[str, dict[str, Any]], evidence_ids: set[str]) -> None:
    effect = _mapping(value, "graph.second_order_effect")
    status = _required_string(effect, "status", "graph.second_order_effect")
    if status == "resolved":
        actor_node_id = _required_string(effect, "actor_node_id", "graph.second_order_effect")
        _require_node(actor_node_id, node_index, "graph.second_order_effect.actor_node_id")
        _required_string(effect, "effect", "graph.second_order_effect")
    elif status == "unresolved":
        _required_string(effect, "rationale", "graph.second_order_effect")
    else:
        _fail("graph.second_order_effect.status must be resolved or unresolved")
    _validate_evidence_refs(effect.get("evidence_refs"), "graph.second_order_effect.evidence_refs", evidence_ids)


def _validate_ownership_concentration(value: Any, node_index: Mapping[str, dict[str, Any]], evidence_ids: set[str]) -> None:
    observations = _sequence(value, "graph.ownership_concentration", minimum=1)
    for position, raw_observation in enumerate(observations):
        path = f"graph.ownership_concentration[{position}]"
        observation = _mapping(raw_observation, path)
        node_id = _required_string(observation, "node_id", path)
        _require_node(node_id, node_index, f"{path}.node_id")
        kind = _required_string(observation, "kind", path)
        if kind not in {"ownership", "concentration"}:
            _fail(f"{path}.kind must be ownership or concentration")
        _required_string(observation, "statement", path)
        vector = _required_string(observation, "vector", path)
        if vector not in CONCENTRATION_VECTORS:
            _fail(f"{path}.vector must be one of {sorted(CONCENTRATION_VECTORS)}")
        _required_string(observation, "rationale", path)
        _validate_evidence_refs(observation.get("evidence_refs"), f"{path}.evidence_refs", evidence_ids)
        if vector == "loosening":
            _required_string(observation, "rating_dependency", path)


def _validate_us_expression(value: Any, node_index: Mapping[str, dict[str, Any]], evidence_ids: set[str]) -> None:
    expression = _mapping(value, "graph.us_expression")
    resolution = _required_string(expression, "resolution", "graph.us_expression")
    if resolution not in VEHICLE_RESOLUTIONS:
        _fail(f"graph.us_expression.resolution must be one of {sorted(VEHICLE_RESOLUTIONS)}")
    listed_expressions = expression.get("listed_expressions")
    if resolution == "no_clean_vehicle":
        _required_string(expression, "rationale", "graph.us_expression")
        _validate_evidence_refs(expression.get("evidence_refs"), "graph.us_expression.evidence_refs", evidence_ids)
        if listed_expressions not in (None, []):
            _fail("no_clean_vehicle cannot include listed expressions")
        return

    primary_listings: list[dict[str, Any]] = []
    for position, raw_listing in enumerate(_sequence(listed_expressions, "graph.us_expression.listed_expressions", minimum=1)):
        path = f"graph.us_expression.listed_expressions[{position}]"
        listing = _mapping(raw_listing, path)
        ticker = _required_string(listing, "ticker", path)
        if ticker != ticker.upper() or not ticker.replace("-", "").replace(".", "").isalnum():
            _fail(f"{path}.ticker must be a normalized ticker")
        node_id = _required_string(listing, "node_id", path)
        node = _require_node(node_id, node_index, f"{path}.node_id")
        if listing.get("market") != "US":
            _fail("listed expression must resolve to a US-listed security")
        _validate_evidence_refs(listing.get("evidence_refs"), f"{path}.evidence_refs", evidence_ids)
        exposure_class = _required_string(listing, "exposure_class", path)
        if exposure_class not in EXPOSURE_CLASSES:
            _fail(f"{path}.exposure_class must be one of {sorted(EXPOSURE_CLASSES)}")
        revenue_link_status = _required_string(listing, "revenue_link_status", path)
        if revenue_link_status not in REVENUE_LINK_STATUSES:
            _fail(f"{path}.revenue_link_status must be one of {sorted(REVENUE_LINK_STATUSES)}")
        if revenue_link_status == "unresolved":
            _required_string(listing, "capture_rationale", path)
            if "capture_evidence_refs" in listing:
                _validate_evidence_refs(listing["capture_evidence_refs"], f"{path}.capture_evidence_refs", evidence_ids)
        else:
            _validate_evidence_refs(listing.get("capture_evidence_refs"), f"{path}.capture_evidence_refs", evidence_ids)
        _validate_node_ids(listing.get("shared_driver_ids"), f"{path}.shared_driver_ids", node_index)
        _validate_node_ids(listing.get("shared_failure_node_ids"), f"{path}.shared_failure_node_ids", node_index)
        role = _required_string(listing, "role", path)
        if role not in EXPRESSION_ROLES:
            _fail(f"{path}.role must be one of {sorted(EXPRESSION_ROLES)}")
        _validate_exposure_compatibility(exposure_class, node["relationship_to_bottleneck"], path)
        if role == "primary":
            primary_listings.append(listing)

    if len(primary_listings) != 1:
        _fail("a vehicle resolution requires exactly one primary listed expression")
    if resolution == "clean_vehicle":
        primary = primary_listings[0]
        if primary["exposure_class"] == "theme_proxy" or primary["revenue_link_status"] == "unresolved":
            _fail("clean_vehicle primary cannot be a theme_proxy or have an unresolved revenue link")


def _validate_exposure_compatibility(exposure_class: str, relationship: str, path: str) -> None:
    compatible_relationships = {
        "owner": {"owns"},
        "partial_owner": {"owns"},
        "supplier_to_owner": {"supplies", "enables"},
        "theme_proxy": {"theme_exposure"},
    }
    if relationship not in compatible_relationships[exposure_class]:
        _fail(f"{path}.exposure_class {exposure_class} is incompatible with node relationship {relationship}")


def _validate_node_ids(value: Any, path: str, node_index: Mapping[str, dict[str, Any]]) -> None:
    node_ids = _id_list(value, path, minimum=1)
    if len(set(node_ids)) != len(node_ids):
        _fail(f"{path} must be distinct")
    for node_id in node_ids:
        _require_node(node_id, node_index, path)


def _validate_claims(value: Any, path: str, evidence_ids: set[str]) -> None:
    claims = _sequence(value, path, minimum=1)
    for position, raw_claim in enumerate(claims):
        claim_path = f"{path}[{position}]"
        claim = _mapping(raw_claim, claim_path)
        _required_string(claim, "statement", claim_path)
        _validate_evidence_refs(claim.get("evidence_refs"), f"{claim_path}.evidence_refs", evidence_ids)


def _validate_evidence_refs(value: Any, path: str, evidence_ids: set[str]) -> None:
    references = _id_list(value, path, minimum=1)
    fabricated = sorted(set(references) - evidence_ids)
    if fabricated:
        _fail(f"{path} contains fabricated evidence reference(s): {', '.join(fabricated)}")


def _require_node(node_id: str, node_index: Mapping[str, dict[str, Any]], path: str) -> dict[str, Any]:
    try:
        return node_index[node_id]
    except KeyError:
        _fail(f"{path} references unknown node: {node_id}")


def _id_set(value: Any, path: str) -> set[str]:
    values = _id_list(value, path, minimum=1)
    if len(set(values)) != len(values):
        _fail(f"{path} must not contain duplicate values")
    return set(values)


def _id_list(value: Any, path: str, *, minimum: int) -> list[str]:
    values = _sequence(value, path, minimum=minimum)
    for position, item in enumerate(values):
        if not isinstance(item, str) or not item.strip():
            _fail(f"{path}[{position}] must be a non-empty string")
    return list(values)


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{path} must be an object")
    return dict(value)


def _sequence(value: Any, path: str, *, minimum: int) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{path} must be an array")
    values = list(value)
    if len(values) < minimum:
        _fail(f"{path} requires at least {minimum} item(s)")
    return values


def _required_string(value: Mapping[str, Any], key: str, path: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate.strip():
        _fail(f"{path}.{key} must be a non-empty string")
    return candidate


def _fail(message: str) -> None:
    raise SectorGraphValidationError(message)
