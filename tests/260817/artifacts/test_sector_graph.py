from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from serenity_core.runtime import canonical_hash
from serenity_core.schema import SchemaViolation, validate_document
from serenity_core.sector_graph import SectorGraphValidationError, build_sector_graph, validate_sector_graph


ROOT = Path(__file__).resolve().parents[3]
SECTOR_SCHEMA = json.loads((ROOT / "schemas" / "sector-graph-1.schema.json").read_text(encoding="utf-8"))


def physical_ai_graph() -> dict:
    evidence_refs = [
        "result-robotics-demand",
        "result-harmonic-drive",
        "result-bearing-steel",
        "result-us-listing",
        "result-vehicle-exposure",
    ]
    return {
        "schema_id": "urn:serenity:schema:sector-graph:1",
        "graph_id": "sector-physical-ai-001",
        "run_id": "run-physical-ai-001",
        "as_of": "2026-08-17",
        "evidence_refs": evidence_refs,
        "nodes": [
            {
                "node_id": "humanoid-robots",
                "node_type": "industry",
                "label": "Humanoid robots",
                "relationship_to_bottleneck": "enables",
                "claims": [{"statement": "Humanoids need motion-control assemblies.", "evidence_refs": ["result-robotics-demand"]}],
            },
            {
                "node_id": "harmonic-drive",
                "node_type": "layer",
                "label": "Harmonic drive",
                "relationship_to_bottleneck": "owns",
                "claims": [{"statement": "Precision harmonic drives constrain actuator throughput.", "evidence_refs": ["result-harmonic-drive"]}],
            },
            {
                "node_id": "bearing-steel",
                "node_type": "input",
                "label": "Bearing-grade steel",
                "relationship_to_bottleneck": "supplies",
                "claims": [{"statement": "Bearing steel qualification is an upstream constraint.", "evidence_refs": ["result-bearing-steel"]}],
            },
            {
                "node_id": "us-harmonic-drive-etf",
                "node_type": "company",
                "label": "US-listed motion-control expression",
                "relationship_to_bottleneck": "theme_exposure",
                "claims": [{"statement": "The security gives US-listed indirect exposure.", "evidence_refs": ["result-us-listing"]}],
            },
        ],
        "edges": [
            {
                "from_node_id": "humanoid-robots",
                "to_node_id": "harmonic-drive",
                "edge_type": "depends_on",
                "claims": [{"statement": "The robot assembly depends on harmonic drives.", "evidence_refs": ["result-robotics-demand"]}],
            },
            {
                "from_node_id": "harmonic-drive",
                "to_node_id": "bearing-steel",
                "edge_type": "depends_on",
                "claims": [{"statement": "Harmonic drives depend on qualified bearing steel.", "evidence_refs": ["result-bearing-steel"]}],
            },
            {
                "from_node_id": "us-harmonic-drive-etf",
                "to_node_id": "harmonic-drive",
                "edge_type": "supplies",
                "claims": [{"statement": "The vehicle is tied to the motion-control layer.", "evidence_refs": ["result-us-listing"]}],
            },
        ],
        "headline_node_id": "harmonic-drive",
        "bottleneck_node_ids": ["harmonic-drive"],
        "recursive_bottom_hop": {
            "node_id": "bearing-steel",
            "path": ["harmonic-drive", "bearing-steel"],
            "stop_rationale": {"reason": "The next supplier tier is fragmented and no scarcity claim is evidenced.", "evidence_refs": ["result-bearing-steel"]},
        },
        "sibling_comparison": {
            "node_ids": ["harmonic-drive", "bearing-steel"],
            "statement": "The drive layer captures a different economic role from the input layer.",
            "evidence_refs": ["result-harmonic-drive", "result-bearing-steel"],
        },
        "second_order_effect": {
            "status": "resolved",
            "actor_node_id": "humanoid-robots",
            "effect": "Assemblers may reserve qualified drive allocation before volume ramps.",
            "evidence_refs": ["result-robotics-demand"],
        },
        "ownership_concentration": [
            {
                "node_id": "harmonic-drive",
                "kind": "concentration",
                "statement": "Qualification capacity is concentrated among a limited set of drive suppliers.",
                "vector": "stable",
                "rationale": "The evidence establishes a limited supplier set but no current change in its breadth.",
                "evidence_refs": ["result-harmonic-drive"],
            }
        ],
        "us_expression": {
            "resolution": "indirect_vehicle",
            "listed_expressions": [
                {
                    "ticker": "ROBO",
                    "node_id": "us-harmonic-drive-etf",
                    "market": "US",
                    "evidence_refs": ["result-us-listing"],
                    "exposure_class": "theme_proxy",
                    "revenue_link_status": "unresolved",
                    "capture_rationale": "The vehicle has thematic exposure, but its revenue capture cannot be resolved from the evidence.",
                    "shared_driver_ids": ["harmonic-drive"],
                    "shared_failure_node_ids": ["bearing-steel"],
                    "role": "primary",
                }
            ],
        },
    }


def saved_evidence_context(graph: dict) -> dict:
    run_manifest = {
        "schema_id": "urn:serenity:schema:run-manifest:2",
        "run_id": graph["run_id"],
        "status": "OPEN",
        "mode": "discovery",
        "question": "Which US-listed expression is relevant to Physical AI?",
        "subjects": ["Physical AI"],
        "as_of": graph["as_of"],
        "started_at": "2026-08-17T00:00:00Z",
        "updated_at": "2026-08-17T00:00:00Z",
        "actor": {"kind": "model", "id": "test-agent"},
        "source_policy": {"policy_id": "fixture", "allow_network": False},
        "events": [{"at": "2026-08-17T00:00:00Z", "type": "run_started"}],
        "artifacts": {},
    }
    run_manifest["content_hash"] = canonical_hash(run_manifest)
    evidence_results = []
    for index, result_id in enumerate(graph["evidence_refs"]):
        result = {
            "schema_id": "urn:serenity:schema:evidence-result:1",
            "result_id": result_id,
            "run_id": graph["run_id"],
            "request_id": f"request-{index:03d}",
            "hypothesis_ids": ["hyp-physical-ai"],
            "capability_id": "sec.filings",
            "availability": "available",
            "provider": "sec",
            "source": {"uri": f"https://example.test/evidence/{index}", "parameters": {}, "canonical_id": f"fixture:{index}"},
            "temporal": {
                "effective_at": "2026-08-01",
                "period_start": "2026-07-01",
                "period_end": "2026-08-01",
                "observed_at": "2026-08-01",
                "available_at": "2026-08-02T00:00:00Z",
                "source_version": "fixture-1",
            },
            "fetched_at": "2026-08-17T00:00:00Z",
            "raw_content_sha256": "a" * 64,
            "transform_version": "fixture/1",
            "identity_bindings": {},
            "fact_refs": [],
            "value": {"fixture": index},
        }
        result["content_hash"] = canonical_hash(result)
        evidence_results.append(result)
    return {"run_manifest": run_manifest, "evidence_results": evidence_results}


def validate_saved_graph(graph: dict) -> dict:
    return validate_sector_graph(graph, **saved_evidence_context(graph))


def test_builds_and_validates_a_physical_ai_chain_with_a_recursive_bottom_hop() -> None:
    graph = physical_ai_graph()
    context = saved_evidence_context(graph)

    built = build_sector_graph(graph, **context)

    assert validate_sector_graph(built, **context) == built
    validate_document(built, "urn:serenity:schema:sector-graph:1")
    Draft202012Validator(SECTOR_SCHEMA).validate(built)
    assert built["recursive_bottom_hop"]["node_id"] == "bearing-steel"
    assert built["us_expression"]["listed_expressions"][0]["ticker"] == "ROBO"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda graph: graph["nodes"][1].update({"relationship_to_bottleneck": "theme_exposure"}),
            "theme exposure",
        ),
        (
            lambda graph: graph.update(
                {
                    "recursive_bottom_hop": {
                        "node_id": "harmonic-drive",
                        "path": ["harmonic-drive"],
                        "stop_rationale": {"reason": "no further work", "evidence_refs": ["result-harmonic-drive"]},
                    }
                }
            ),
            "distinct",
        ),
        (
            lambda graph: graph["edges"].append(
                {
                    "from_node_id": "bearing-steel",
                    "to_node_id": "humanoid-robots",
                    "edge_type": "depends_on",
                    "claims": [{"statement": "This makes the dependency graph cyclic.", "evidence_refs": ["result-bearing-steel"]}],
                }
            ),
            "cycle",
        ),
        (
            lambda graph: graph.update({"us_expression": {"resolution": "clean_vehicle", "listed_expressions": [{"ticker": "FOREIGN", "node_id": "harmonic-drive", "market": "JP", "evidence_refs": ["result-us-listing"]}]}}),
            "US-listed",
        ),
        (
            lambda graph: graph.update({"us_expression": {"resolution": "no_clean_vehicle"}}),
            "rationale",
        ),
        (
            lambda graph: graph["nodes"][1]["claims"][0].update({"evidence_refs": ["result-invented"]}),
            "fabricated",
        ),
    ],
)
def test_rejects_near_miss_chain_or_unresolved_foreign_vehicle(mutate, message: str) -> None:
    graph = physical_ai_graph()
    mutate(graph)

    with pytest.raises(SectorGraphValidationError, match=message):
        validate_saved_graph(graph)


def test_concentration_requires_a_directional_vector_and_reassessment_when_loosening() -> None:
    graph = physical_ai_graph()
    observation = graph["ownership_concentration"][0]
    observation.pop("vector")

    with pytest.raises(SchemaViolation, match="vector"):
        validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="vector"):
        validate_saved_graph(graph)

    graph = physical_ai_graph()
    observation = graph["ownership_concentration"][0]
    observation["vector"] = "loosening"

    with pytest.raises(SchemaViolation, match="rating_dependency"):
        validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="rating_dependency"):
        validate_saved_graph(graph)

    observation["rating_dependency"] = "Reassess the ownership claim if qualified capacity broadens."
    validate_document(graph, "urn:serenity:schema:sector-graph:1")
    validate_saved_graph(graph)


def test_us_vehicle_attribution_requires_one_primary_and_blocks_false_clean_owner_claims() -> None:
    graph = physical_ai_graph()
    listing = graph["us_expression"]["listed_expressions"][0]
    listing.pop("exposure_class")

    with pytest.raises(SchemaViolation, match="exposure_class"):
        validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="exposure_class"):
        validate_saved_graph(graph)

    graph = physical_ai_graph()
    graph["us_expression"]["resolution"] = "clean_vehicle"
    graph["us_expression"]["listed_expressions"][0]["revenue_link_status"] = "unresolved"

    with pytest.raises(SchemaViolation, match="theme_proxy"):
        validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="clean_vehicle"):
        validate_saved_graph(graph)

    graph = physical_ai_graph()
    duplicate = dict(graph["us_expression"]["listed_expressions"][0])
    duplicate["ticker"] = "BOTZ"
    graph["us_expression"]["listed_expressions"].append(duplicate)

    with pytest.raises(SchemaViolation, match="Too many items match"):
        validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="exactly one primary"):
        validate_saved_graph(graph)

    graph = physical_ai_graph()
    listing = graph["us_expression"]["listed_expressions"][0]
    listing.update({"exposure_class": "owner", "revenue_link_status": "deduced", "capture_evidence_refs": ["result-vehicle-exposure"]})
    listing.pop("capture_rationale")

    validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="incompatible"):
        validate_saved_graph(graph)

    graph = physical_ai_graph()
    graph["us_expression"]["listed_expressions"][0]["shared_driver_ids"].append("harmonic-drive")

    with pytest.raises(SchemaViolation, match="non-unique"):
        validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="must be distinct"):
        validate_saved_graph(graph)

    graph = physical_ai_graph()
    graph["us_expression"]["listed_expressions"][0]["capture_evidence_refs"] = ["result-invented"]

    validate_document(graph, "urn:serenity:schema:sector-graph:1")
    with pytest.raises(SectorGraphValidationError, match="fabricated"):
        validate_saved_graph(graph)


def test_no_clean_vehicle_and_unknown_concentration_remain_explicitly_representable() -> None:
    graph = physical_ai_graph()
    graph["ownership_concentration"][0]["vector"] = "unknown"
    graph["us_expression"] = {
        "resolution": "no_clean_vehicle",
        "rationale": "No US-listed vehicle has a demonstrated revenue link to the bottleneck.",
        "evidence_refs": ["result-us-listing"],
    }

    validate_document(graph, "urn:serenity:schema:sector-graph:1")
    validate_saved_graph(graph)


def test_graph_evidence_refs_bind_to_saved_hash_valid_results_from_the_same_run() -> None:
    graph = physical_ai_graph()
    context = saved_evidence_context(graph)

    validate_sector_graph(graph, **context)

    context["evidence_results"][0]["content_hash"] = "0" * 64
    with pytest.raises(SectorGraphValidationError, match="content_hash"):
        validate_sector_graph(graph, **context)

    context = saved_evidence_context(graph)
    graph["evidence_refs"].append("result-not-saved")
    with pytest.raises(SectorGraphValidationError, match="saved evidence result"):
        validate_sector_graph(graph, **context)

    graph = physical_ai_graph()
    context = saved_evidence_context(graph)
    context["evidence_results"][0]["run_id"] = "run-other"
    context["evidence_results"][0]["content_hash"] = canonical_hash(
        {key: value for key, value in context["evidence_results"][0].items() if key != "content_hash"}
    )
    with pytest.raises(SectorGraphValidationError, match="does not match the run manifest"):
        validate_sector_graph(graph, **context)


def test_graph_run_and_as_of_must_match_the_saved_run_context() -> None:
    graph = physical_ai_graph()
    context = saved_evidence_context(graph)
    graph["as_of"] = "2026-08-18"

    with pytest.raises(SectorGraphValidationError, match="as_of"):
        validate_sector_graph(graph, **context)

    graph = physical_ai_graph()
    context = saved_evidence_context(graph)
    graph["run_id"] = "run-other"
    with pytest.raises(SectorGraphValidationError, match="run_id"):
        validate_sector_graph(graph, **context)
