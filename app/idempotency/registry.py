import asyncio
import time
from typing import Dict, Optional, Any

class IdempotencyRegistry:
    def __init__(self, ttl_seconds: int = 86400):
        # Almacenamiento en memoria RAM volátil para el Edge
        self._storage: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self.ttl_seconds = ttl_seconds

    async def register_request(self, idempotency_key: str, user_id: str) -> bool:
        """
        Intenta registrar la clave. Devuelve True si es nueva (Miss),
        o False si ya existe (Hit / Duplicado).
        """
        async with self._lock:
            current_time = time.time()
            
            # Verificar si la clave existe y sigue vigente
            if idempotency_key in self._storage:
                record = self._storage[idempotency_key]
                if current_time - record["created_at"] < self.ttl_seconds:
                    return False  # ! HIT DETECTADO (Frena el duplicado)
                
            # Registrar nueva "chispa" (Miss)
            self._storage[idempotency_key] = {
                "user_id": user_id,
                "status": "PENDING",
                "response_payload": None,
                "created_at": current_time
            }
            return True

    async def set_response(self, idempotency_key: str, response: bytes) -> None:
        """Guarda la respuesta una vez procesada la transacción."""
        async with self._lock:
            if idempotency_key in self._storage:
                self._storage[idempotency_key]["status"] = "COMPLETED"
                self._storage[idempotency_key]["response_payload"] = response

    async def clean_expired(self) -> None:
        """Limpieza asíncrona manual de llaves expiradas (Evita fugas de memoria)."""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                k for k, v in self._storage.items() 
                if current_time - v["created_at"] >= self.ttl_seconds
            ]
            for k in expired_keys:
                del self._storage[k]
