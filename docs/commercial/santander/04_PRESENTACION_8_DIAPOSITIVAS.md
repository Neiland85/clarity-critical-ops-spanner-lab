# Clarity Critical Operations
## Evaluación técnica para resiliencia de operaciones críticas

**Clarity Structures Digital S.L.**<br>
Neil Muñoz Lago

---

# 1. El problema

Retries, redeliveries, callbacks, timeouts y workers concurrentes pueden provocar operaciones duplicadas, decisiones contradictorias y resultados inciertos.

---

# 2. Qué propone Clarity

Una capa neutral para identificar cada intención, decidir si crear, esperar, reproducir o rechazar, asignar leases, aplicar fencing y conservar evidencia.

---

# 3. Cómo funciona

```text
ExecutionEnvelope
→ Scope + identidad
→ Registro autoritativo
→ Lease + fencing
→ Operación / reconciliación
→ Resultado y evidencia
```

---

# 4. Estado técnico actual

- núcleo implementado;
- memoria y Google Cloud Spanner;
- snapshots inmutables;
- payloads congelados;
- scope obligatorio;
- `CONFLICT` sin payload;
- **106 tests superados**.

---

# 5. Evidencia y límites

**Verificado:** comportamiento local, contract tests, leases, fencing, replay, conflictos y pruebas adversariales.

**No afirmado:** producción, exactly-once end-to-end, alta disponibilidad, cumplimiento DORA o validación en Spanner real.

---

# 6. Riesgo pendiente

Si un proveedor ejecuta pero la respuesta se pierde, repetir puede duplicar el efecto.

Próximo gate: `OUTCOME_UNKNOWN`, reconciliación, política de retry y pruebas de crash y timeout.

---

# 7. Primer caso recomendado

Un flujo interno, no monetario, reversible o reconciliable, con datos sintéticos y criterios medibles.

Ámbitos: onboarding, validación documental, callbacks, notificaciones críticas, back-office o conciliación.

---

# 8. Decisión solicitada

Reunión técnica de 45 minutos para identificar el caso, el propietario operativo, la criticidad, los datos y el siguiente paso.

**Neil Muñoz Lago**<br>
Clarity Structures Digital S.L.<br>
613 722 441<br>
admin@claritystructures.com
