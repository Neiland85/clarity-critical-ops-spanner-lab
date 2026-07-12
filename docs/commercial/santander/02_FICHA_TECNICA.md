# Clarity Critical Operations
## Ficha técnica para evaluación inicial

**Titular:** Clarity Structures Digital S.L.<br>
**Responsable:** Neil Muñoz Lago<br>
**Clasificación técnica:** Provider-Neutral Critical Execution Control Plane<br>
**Estado:** núcleo técnico prepiloto<br>
**Baseline de referencia:** `bb2f27b`

## 1. Finalidad

Clarity Critical Operations controla la admisión, ejecución, repetición, recuperación y evidencia de operaciones críticas sometidas a:

- retries;
- redeliveries;
- callbacks repetidos;
- concurrencia;
- timeouts;
- reconexiones;
- caídas de workers;
- respuestas ambiguas de proveedores.

Su finalidad es reducir el riesgo de que una misma intención produzca efectos duplicados, contradictorios o difíciles de reconstruir.

No sustituye al core bancario, ledger, sistema de registro ni proveedor de identidad. Actúa como una capa de control entre canales, servicios internos y proveedores.

## 2. Arquitectura

```text
Canal o sistema origen
        |
        v
ExecutionEnvelope
        |
        v
Validación de identidad y scope
        |
        v
Registro autoritativo de idempotencia
        |
        v
Lease de ejecución y fencing
        |
        v
Operación de dominio o integración
        |
        v
Resultado, reconciliación y evidencia
El diseño separa:

- contrato de ejecución;
- decisión idempotente;
- almacenamiento autoritativo;
- lógica de dominio;
- integración con proveedores;
- evidencia operativa.

El almacenamiento se encuentra detrás de un puerto neutral. Actualmente existen:

- implementación de referencia en memoria;
- adaptador para Google Cloud Spanner.

## 3. Invariantes actuales

El núcleo implementa y prueba localmente:

1. una misma combinación de scope y clave identifica una única intención;
2. una clave reutilizada con una petición distinta produce conflicto;
3. una operación pendiente no entrega un segundo lease activo;
4. un resultado completado puede reproducirse sin reejecutar;
5. un worker con un lease obsoleto no puede persistir una transición terminal;
6. el intento aumenta cuando una operación es reacquirida;
7. memoria y Spanner comparten el mismo contrato público;
8. los records públicos se entregan como snapshots inmutables;
9. los payloads anidados se congelan profundamente;
10. una respuesta `CONFLICT` no expone payloads previos;
11. el scope es obligatorio;
12. los límites de identidad se validan de forma común.

## 4. Semántica de valores

La autoridad interna no se expone directamente.

Los consumidores reciben snapshots inmutables. Esto impide que un caller pueda:

- modificar el estado fuera del registro;
- alterar un lease;
- cambiar el número de intento;
- mutar payloads anidados;
- saltarse el lock o las reglas de transición.

Esta corrección responde a una auditoría adversarial independiente y está cubierta por pruebas específicas de aliasing, mutación y divulgación de payload.

## 5. Adaptador Cloud Spanner

El adaptador utiliza primitivas reales del SDK:

- `run_in_transaction`;
- lecturas transaccionales;
- `insert`;
- `update`;
- tiempo autoritativo mediante `CURRENT_TIMESTAMP()`;
- clave primaria compuesta por scope y clave idempotente.

Actualmente está validado mediante una suite contractual ejecutada contra un doble transaccional.

Todavía no se afirma:

- validación contra Spanner Emulator;
- validación contra una instancia real;
- convergencia multiproceso;
- comportamiento ante `ABORTED`;
- resolución de commit con resultado desconocido;
- recuperación distribuida;
- preparación para producción.

## 6. Evidencia técnica actual

Baseline verificada:

- **106 tests automatizados superados**;
- Black limpio;
- isort limpio;
- Bandit sin hallazgos medios o altos;
- `pip check` sin dependencias incompatibles;
- `pip-audit` sin vulnerabilidades conocidas en runtime y desarrollo;
- CI de calidad y seguridad en verde;
- contract tests para memoria y Spanner;
- pruebas adversariales de mutabilidad y aislamiento.

La evidencia actual acredita comportamiento local y contractual. No se extrapola a producción ni a comportamiento distribuido.

## 7. Riesgo técnico todavía abierto

El principal riesgo pendiente es el resultado externo ambiguo.

Ejemplo:

1. un worker adquiere un lease;
2. llama a un proveedor;
3. el proveedor ejecuta la operación;
4. la respuesta se pierde;
5. el worker cae antes de persistir `COMPLETED`;
6. el lease expira;
7. otro worker podría repetir la operación.

El fencing actual protege la escritura terminal en el registro, pero no garantiza por sí solo que un proveedor externo no ejecute dos veces.

El siguiente gate técnico incluye:

- estado `OUTCOME_UNKNOWN`;
- reconciliación;
- política de retry por tipo de operación;
- downstream idempotency;
- pruebas de crash y timeout.

## 8. Caso de evaluación recomendado

La primera evaluación debe utilizar un flujo:

- interno;
- no monetario;
- acotado;
- reversible o reconciliable;
- con datos sintéticos o anonimizados;
- con criterios de aceptación medibles.

Ejemplos:

- validación documental;
- onboarding;
- back-office;
- notificaciones críticas;
- callbacks de terceros;
- procesos de conciliación operativa.

No se recomienda comenzar por transferencias, pagos ni instrucciones financieras irreversibles.

## 9. Forma de integración

Opciones iniciales:

- librería dentro de un servicio;
- servicio interno mediante API;
- capa delante de un proveedor;
- control de callbacks o webhooks;
- coordinador de trabajos asíncronos.

La elección debe depender del caso, de la frontera transaccional y del sistema que mantenga la verdad de negocio.

## 10. Propuesta de evaluación

Primera sesión técnica de 45 minutos para:

1. identificar un flujo con retries o resultados ambiguos;
2. determinar el propietario operativo;
3. definir volumen, criticidad y datos;
4. fijar criterios de éxito;
5. decidir si procede una discovery técnica o prueba controlada.

## 11. Límites expresos

Clarity Critical Operations no se presenta actualmente como:

- producto production-ready;
- solución de cumplimiento DORA;
- core bancario;
- plataforma Kubernetes;
- sistema exactly-once end-to-end;
- servicio de alta disponibilidad;
- sistema validado bajo carga industrial.

La propuesta es evaluar un núcleo técnico prepiloto sobre un caso controlado.

---

**Neil Muñoz Lago**<br>
Administrador<br>
**Clarity Structures Digital S.L.**<br>
613 722 441<br>
admin@claritystructures.com
