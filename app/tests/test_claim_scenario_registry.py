from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = ROOT / "tests" / "resilience" / "scenarios.yaml"
CLAIMS_PATH = ROOT / "claims" / "claims.yaml"
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
GATE_PATTERN = re.compile(r"^V[0-6]$")
LAYER_PATTERN = re.compile(r"^L[0-5]$")


def _load_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path} must contain a mapping"
    return payload


def _assert_unique(values: list[str], label: str) -> None:
    assert len(values) == len(set(values)), f"duplicate {label}: {values}"


def _reference_path(reference: str) -> Path:
    return ROOT / reference.split("::", maxsplit=1)[0]


def _assert_references_exist(references: list[str], label: str) -> None:
    for reference in references:
        assert (
            isinstance(reference, str) and reference.strip()
        ), f"{label} contains an empty reference"
        path = _reference_path(reference)
        assert path.exists(), f"{label} references missing path: {reference}"


def test_resilience_catalogue_schema_and_identifiers() -> None:
    catalogue = _load_mapping(SCENARIOS_PATH)

    assert catalogue["schema_version"] == "1.0"
    assert isinstance(catalogue["catalogue"], dict)
    assert isinstance(catalogue["defaults"], dict)
    assert isinstance(catalogue["invariants"], dict)
    assert isinstance(catalogue["scenarios"], list)

    status_values = catalogue["status_values"]
    implementation_statuses = set(status_values["implementation_status"])
    validation_statuses = set(status_values["validation_status"])
    invariant_ids = set(catalogue["invariants"])
    scenarios = catalogue["scenarios"]
    scenario_ids = [scenario["id"] for scenario in scenarios]

    _assert_unique(scenario_ids, "scenario identifiers")
    assert scenario_ids, "scenario catalogue must not be empty"

    for scenario in scenarios:
        required = {
            "id",
            "version",
            "title",
            "gate",
            "layer",
            "implementation_status",
            "validation_status",
            "expected",
            "invariants",
            "metrics",
        }
        assert (
            required <= scenario.keys()
        ), f"{scenario.get('id')} is missing {required - scenario.keys()}"
        assert GATE_PATTERN.fullmatch(scenario["gate"])
        assert LAYER_PATTERN.fullmatch(scenario["layer"])
        assert scenario["implementation_status"] in implementation_statuses
        assert scenario["validation_status"] in validation_statuses
        assert scenario["expected"], f"{scenario['id']} must define expected results"
        assert scenario["metrics"], f"{scenario['id']} must define metrics"
        assert set(scenario["invariants"]) <= invariant_ids
        if scenario["implementation_status"] != "BLOCKED":
            assert scenario.get("stimulus") or scenario.get(
                "fault_profile"
            ), f"{scenario['id']} must define stimulus or fault_profile"


def test_scenario_status_contracts_and_test_references() -> None:
    catalogue = _load_mapping(SCENARIOS_PATH)

    for scenario in catalogue["scenarios"]:
        identifier = scenario["id"]
        implementation_status = scenario["implementation_status"]
        validation_status = scenario["validation_status"]
        test_refs = scenario.get("test_refs", [])

        if implementation_status == "AUTOMATED_LOCAL":
            assert validation_status == "BASELINE_LOCAL"
            assert test_refs, f"{identifier} must reference an automated test"
            _assert_references_exist(test_refs, f"scenario {identifier} test_refs")

        if implementation_status == "BLOCKED":
            assert scenario.get(
                "blocked_by"
            ), f"{identifier} must explain what blocks execution"
            assert validation_status == "NOT_EXECUTED"

        if validation_status in {"PASS", "FAIL", "ABORTED", "INVALIDATED"}:
            assert scenario.get(
                "evidence"
            ), f"{identifier} must reference preserved execution evidence"


def test_claim_registry_schema_and_identifiers() -> None:
    registry = _load_mapping(CLAIMS_PATH)

    assert registry["schema_version"] == "1.0"
    assert isinstance(registry["registry"], dict)
    assert isinstance(registry["rules"], list)
    assert isinstance(registry["current_verified_boundary"], dict)
    assert isinstance(registry["claims"], list)
    assert isinstance(registry["forbidden_statements"], list)

    allowed_statuses = set(registry["status_values"])
    claims = registry["claims"]
    claim_ids = [claim["id"] for claim in claims]
    rule_ids = [rule["id"] for rule in registry["rules"]]
    forbidden_ids = [item["id"] for item in registry["forbidden_statements"]]

    _assert_unique(claim_ids, "claim identifiers")
    _assert_unique(rule_ids, "claim rule identifiers")
    _assert_unique(forbidden_ids, "forbidden-statement identifiers")

    for claim in claims:
        required = {
            "id",
            "statement",
            "status",
            "public_use",
            "scope",
            "required_gate",
            "scenarios",
            "evidence",
            "limitations",
            "last_validation_date",
            "repository_commit",
            "owner",
        }
        assert (
            required <= claim.keys()
        ), f"{claim.get('id')} is missing {required - claim.keys()}"
        assert claim["status"] in allowed_statuses
        assert GATE_PATTERN.fullmatch(claim["required_gate"])
        assert claim["statement"].strip()
        assert claim["scope"].strip()
        assert claim["limitations"], f"{claim['id']} must state limitations"


def test_claim_scenario_and_evidence_references_resolve() -> None:
    catalogue = _load_mapping(SCENARIOS_PATH)
    registry = _load_mapping(CLAIMS_PATH)
    scenario_ids = {scenario["id"] for scenario in catalogue["scenarios"]}

    _assert_references_exist(
        catalogue["catalogue"].get("related", []),
        "scenario catalogue related documents",
    )
    _assert_references_exist(
        registry["registry"].get("related", []),
        "claim registry related documents",
    )

    for claim in registry["claims"]:
        identifier = claim["id"]
        missing = set(claim["scenarios"]) - scenario_ids
        assert not missing, f"{identifier} references unknown scenarios: {missing}"
        _assert_references_exist(claim["evidence"], f"claim {identifier} evidence")


def test_verified_claims_have_validation_metadata() -> None:
    registry = _load_mapping(CLAIMS_PATH)
    verified_statuses = {
        "VERIFIED_LOCAL",
        "VERIFIED_DISTRIBUTED",
        "VERIFIED_PREPRODUCTION",
    }

    for claim in registry["claims"]:
        if claim["status"] not in verified_statuses:
            continue

        assert claim["evidence"], f"{claim['id']} has no evidence"
        assert claim["last_validation_date"], f"{claim['id']} has no validation date"
        repository_commit = claim["repository_commit"]
        assert isinstance(repository_commit, str)
        assert COMMIT_SHA_PATTERN.fullmatch(
            repository_commit
        ), f"{claim['id']} has an invalid repository commit"


def test_current_verified_boundary_is_narrow_and_evidenced() -> None:
    registry = _load_mapping(CLAIMS_PATH)
    boundary = registry["current_verified_boundary"]

    assert boundary["status"] == "VERIFIED_LOCAL"
    assert boundary["topology"] == "single Python process"
    assert boundary["test_suite"]["collected"] == boundary["test_suite"]["passed"]
    assert boundary["verified_properties"]
    assert boundary["not_verified"]
    assert COMMIT_SHA_PATTERN.fullmatch(boundary["repository_commit"])
