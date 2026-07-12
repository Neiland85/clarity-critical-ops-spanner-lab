# Clarity Critical Operations — Asset Manifest

## 1. Identidad del activo

**Nombre:** Clarity Critical Operations<br>
**Clase técnica:** Provider-Neutral Critical Execution Control Plane<br>
**Titular:** Clarity Structures Digital S.L.<br>
**Responsable:** Neil Muñoz Lago<br>
**Estado:** `ACTIVE — PRESENTABLE — PREPILOT`<br>
**Baseline de referencia:** `8494952`<br>
**Repositorio autoritativo:** `clarity-critical-ops-spanner-lab`

## 2. Finalidad

Clarity Critical Operations controla la admisión, ejecución, repetición, recuperación y evidencia de operaciones críticas expuestas a:

- retries;
- redeliveries;
- callbacks repetidos;
- concurrencia;
- timeouts;
- caídas de workers;
- comportamiento inestable de proveedores;
- resultados externos ambiguos.

Su finalidad es reducir el riesgo de efectos duplicados, decisiones contradictorias y operaciones difíciles de reconstruir.

No es un core bancario, ledger, plataforma Kubernetes, sistema de pagos ni implementación universal de exactly-once.

## 3. Componentes principales

- `ExecutionEnvelope` versionado;
- hashing canónico;
- registro de idempotencia en memoria;
- puerto provider-neutral `IdempotencyRegistry`;
- adaptador Google Cloud Spanner;
- leases de ejecución;
- fencing de workers obsoletos;
- snapshots públicos inmutables;
- congelación profunda de payloads;
- validación compartida de identidad;
- catálogo de claims;
- escenarios de resiliencia;
- workflows de calidad y seguridad.

## 4. Evidencia actual

Baseline verificada:

- 106 tests automatizados superados;
- Black e isort limpios;
- Bandit sin hallazgos medios o altos;
- `pip check` limpio;
- `pip-audit` sin vulnerabilidades conocidas en runtime y desarrollo;
- contract tests para memoria y Spanner;
- pruebas adversariales de aliasing, mutación y divulgación;
- P0-01 de semántica de valores cerrado;
- CI de calidad y seguridad en verde.

## 5. Límite de validación

Actualmente se acredita:

- comportamiento local;
- contratos provider-neutral;
- leases y fencing del registro;
- snapshots inmutables;
- replay y conflicto;
- adaptador Spanner implementado;
- paridad contractual mediante doble transaccional.

Todavía no se acredita:

- validación contra Spanner Emulator;
- validación contra Spanner real;
- convergencia multiproceso;
- recuperación tras crash o restart;
- resolución de commit con resultado desconocido;
- coordinación atómica con dominio y outbox;
- prevención end-to-end de efectos externos duplicados;
- producción;
- alta disponibilidad;
- cumplimiento DORA o certificación regulatoria.

## 6. Riesgo técnico principal pendiente

El principal riesgo abierto es el resultado externo ambiguo.

Si un proveedor ejecuta una operación, pero la respuesta se pierde antes de persistir `COMPLETED`, la expiración del lease podría permitir una repetición del efecto.

El siguiente gate debe introducir:

- `OUTCOME_UNKNOWN`;
- reconciliación;
- política de retry por tipo de operación;
- downstream idempotency;
- pruebas de crash y timeout.

## 7. Estado comercial

El activo es presentable para:

- evaluación técnica;
- discovery;
- selección de caso de uso;
- diseño de piloto controlado;
- conversaciones de licencia;
- partnership estratégico;
- adquisición de tecnología o IP.

La primera evaluación debe utilizar un flujo interno, no monetario, reversible o reconciliable y con datos sintéticos o anonimizados.

## 8. Modelos de explotación posibles

- servicio de discovery técnica;
- hardening e integración;
- piloto controlado;
- licencia de uso;
- licencia por sector o territorio;
- partnership tecnológico;
- licencia con soporte;
- transferencia de IP;
- adquisición del activo o de la sociedad.

Los importes, red lines y escenarios económicos se mantienen en documentación confidencial externa al repositorio.

## 9. Propiedad intelectual

El código, contratos, documentación, diseños, pruebas, modelos de amenaza, claims y materiales asociados son propiedad de Clarity Structures Digital S.L., salvo componentes de terceros sujetos a sus licencias.

El acceso al repositorio no concede derechos de:

- explotación;
- reproducción;
- modificación;
- sublicencia;
- comercialización;
- despliegue;
- creación de derivados.

Cualquier evaluación, piloto, licencia, partnership o adquisición requiere acuerdo escrito independiente.

## 10. Eventos de revaloración

Debe revisarse el estado del activo cuando ocurra cualquiera de estos hitos:

1. cierre del modelo `OUTCOME_UNKNOWN`;
2. validación con Spanner Emulator;
3. validación multiproceso y restart;
4. integración de una operación vertical;
5. creación del runtime CCO autoritativo;
6. firma de una discovery o piloto;
7. validación por una entidad financiera;
8. licencia, exclusividad, partnership o adquisición.

## 11. Documentación confidencial externa

La valoración económica, precios objetivo, derechos concedidos, exclusividades y límites de negociación se mantienen fuera de este repositorio.

Documento de referencia externo:

`CLARITY_CCO_MANIFIESTO_ACTIVO_VALORACION_20260712_FINAL`

---

**Última actualización:** 12 de julio de 2026<br>
**Baseline:** `8494952`<br>
**Owner:** Clarity Structures Digital S.L.
