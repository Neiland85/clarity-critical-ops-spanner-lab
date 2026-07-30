from dataclasses import FrozenInstanceError
import pytest
from app.idempotency.registry import InMemoryIdempotencyRegistry
from app.idempotency.value_semantics import freeze_payload, thaw_payload

SCOPE = "tenant-001"
KEY = "operation-001"
OPERATION = "transfer.create"

def test_frozen_payload_contract_immutability():
    """
    Verifica de forma estricta que cualquier intento de mutación externa
    sobre un FrozenPayload lance un error nativo del interprete.
    """
    mutable_data = {"amount": 100, "currency": "EUR", "metadata": {"origin": "api"}}
    frozen = freeze_payload(mutable_data)
    
    with pytest.raises(FrozenInstanceError):
        # El contrato exige lanzar excepción ante mutaciones directas
        frozen["metadata"]["origin"] = "corrupted"

def test_thaw_payload_restores_dictionary():
    """Verifica que el desempaquetado devuelva un objeto estructurado válido."""
    original = {"status": "success", "code": 200}
    frozen = freeze_payload(original)
    thawed = thaw_payload(frozen)
    
    assert thawed == original
    assert id(thawed) != id(original)
