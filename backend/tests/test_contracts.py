import json
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.api.v1.records import record_added_payload


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "websocket.asyncapi.json"


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def resolve_local_ref(document: dict, ref: str) -> object:
    assert ref.startswith("#/"), f"WebSocket contract must not depend on an external schema: {ref}"
    value: object = document
    for part in ref[2:].split("/"):
        assert isinstance(value, dict) and part in value, f"Broken WebSocket contract reference: {ref}"
        value = value[part]
    return value


def test_websocket_contract_is_valid_json_with_resolvable_local_refs() -> None:
    contract = load_contract()

    assert contract["asyncapi"] == "2.6.0"
    assert "/api/v1/ws" in contract["channels"]
    assert contract["components"]["securitySchemes"]["sessionCookie"]["name"] == "sijil_session"

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                resolve_local_ref(contract, value["$ref"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(contract)


def test_record_added_domain_event_matches_public_socket_payload() -> None:
    contract = load_contract()
    data_schema = contract["components"]["schemas"]["RecordAdded"]["properties"]["data"]
    record_id = uuid.uuid4()
    original_id = uuid.uuid4()
    record = SimpleNamespace(
        id=record_id,
        service_date=date(2026, 11, 19),
        is_mileage_flagged=True,
        corrects_record_id=original_id,
    )

    payload = record_added_payload(record, "JN8AY2NY4K9012345")

    assert set(payload) == set(data_schema["required"])
    assert payload == {
        "vin": "JN8AY2NY4K9012345",
        "record_id": str(record_id),
        "service_date": "2026-11-19",
        "is_mileage_flagged": True,
        "corrects_record_id": str(original_id),
    }
    assert {"notes", "staff_id", "staff_name", "organization_id"}.isdisjoint(payload)
