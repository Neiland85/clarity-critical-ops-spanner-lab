# Clarity Critical Operations
## Propuesta de evaluación técnica para resiliencia de operaciones críticas

**Clarity Structures Digital S.L.**

### Problema

Los sistemas críticos reciben reintentos, redeliveries, callbacks repetidos, timeouts, reconexiones y ejecuciones concurrentes.

Cuando una operación atraviesa varios sistemas o proveedores, estas condiciones pueden provocar:

- efectos duplicados;
- decisiones contradictorias;
- operaciones bloqueadas o repetidas;
- resultados difíciles de reconstruir;
- pérdida de trazabilidad sobre qué ocurrió realmente.

El riesgo más complejo aparece cuando un proveedor ejecuta una operación, pero la respuesta se pierde: el sistema debe decidir si repetir, esperar o reconciliar sin producir un segundo efecto.

### Qué es Clarity Critical Operations

Clarity Critical Operations es una capa tecnológica neutral para controlar la ejecución de operaciones críticas.

Su núcleo modela:

- contratos de ejecución versionados;
- identidad idempotente por operación y ámbito;
- detección de duplicados y conflictos;
- leases de ejecución;
- fencing de workers obsoletos;
- replay controlado;
- persistencia autoritativa;
- trazabilidad y evidencia operativa.

No sustituye al core bancario ni al sistema de registro principal. Se sitúa entre los canales, servicios y proveedores para controlar cómo se admite, ejecuta, repite y recupera una operación crítica.

### Aplicación bancaria inicial

La propuesta no consiste en desplegar una plataforma completa.

El primer objetivo sería seleccionar un único flujo interno, no monetario y acotado, en el que existan:

- reintentos;
- timeouts;
- callbacks o redeliveries;
- proveedores externos;
- necesidad de reconstrucción o reconciliación.

Ejemplos posibles: onboarding, validación documental, back-office, conciliación operativa, notificaciones críticas o integración con terceros.

### Estado técnico actual

El proyecto se encuentra en fase **prepiloto técnico**.

Actualmente dispone de:

- núcleo de ejecución e idempotencia implementado;
- adaptadores de memoria y Google Cloud Spanner;
- semántica de valores endurecida con snapshots inmutables;
- aislamiento explícito por scope;
- pruebas adversariales de aliasing, mutación y conflictos;
- 106 tests automatizados superados;
- análisis de formato, dependencias y seguridad sin hallazgos bloqueantes.

El adaptador Spanner está implementado, pero todavía no se presenta como validado en producción ni como comportamiento distribuido demostrado.

El siguiente gate técnico es validar resultados ambiguos, reconciliación y comportamiento frente a fallos reales antes de cualquier piloto.

### Alcance de la propuesta

Se solicita una reunión exploratoria de aproximadamente 45 minutos con responsables de:

- arquitectura tecnológica;
- resiliencia operativa;
- riesgo TIC;
- integración crítica;
- innovación aplicada.

La reunión tendría cuatro objetivos:

1. presentar el problema técnico;
2. mostrar la evidencia disponible;
3. identificar un caso de uso interno adecuado;
4. determinar si procede diseñar una prueba controlada.

### Decisión solicitada

No se solicita una decisión de compra.

Se solicita únicamente una **evaluación técnica inicial** para determinar si existe encaje con un caso de uso real del banco.

---

**Neil Muñoz Lago**<br>
Administrador<br>
**Clarity Structures Digital S.L.**<br>
613 722 441<br>
admin@claritystructures.com
