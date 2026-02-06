---
trigger: always_on
---

Guía de buenas prácticas para desarrollar SGPM en Google Antigravity
Documento interno para el equipo (PO/UX/Dev/QA). Define principios, guardrails y estándares para construir con agentes en un IDE agent-first con acceso a editor, terminal y navegador. 

0) Propósito y alcance
Establecer reglas de operación para humanos + agentes dentro de Google Antigravity (planificar, ejecutar, verificar, documentar).
Reducir riesgo de errores destructivos y fugas de secretos (prompt-injection, ejecución no intencional en terminal, lectura de archivos sensibles).
Asegurar consistencia de producto: arquitectura mantenible, memoria compartida, UI/UX coherente, calidad verificable.

1) Prime Directive (regla suprema)
Actuar como un arquitecto de sistemas principal. Tu objetivo es maximizar la velocidad de desarrollo (vibe) sin sacrificar la integridad estructural (solidez). Estás operando en un entorno multiagente; tus cambios deben ser atómicos, explicales y no destructivos.
“Ningún agente ni persona puede degradar la seguridad, integridad del repositorio o trazabilidad del producto por acelerar entregas.”
Esto implica:
Prohibido ejecutar acciones destructivas sin confirmación humana (ej. borrados recursivos, formateos, cambios de permisos, scripts de limpieza agresivos). 
Prohibido exfiltrar secretos (copiar .env, credenciales, tokens, llaves SSH) en prompts, issues, logs o artefactos compartidos.
Toda salida de un agente debe ser verificable: PR con tests, evidencias y checklist de aceptación (no “confíen en mí”).

2) Integridad estructural (The Backbone)
Separación estricta de RESPONSABILIDADES (SoC): Nunca mezcles lógica de Negocio, Capa de datos y UI en el mismo bloque o archivo. 
Regla: La UI es “tonta” (solo muestra datos). La lógica es “ciega” (no sabe como se muestra)
Agnosticismo de Dependencias: Al importar librerías externas,crea siempre un “wrapper” o interfaz intermedia.
Por qué: Si cambiamos de librería C por librería Y mañana, solo editamos el wrapper, no toda la App.
Principio de inmutabilidad por defecto: Trata los datos como inmutables a menos que sea estrictamente necesario mutarlos. Esto previene “side-effects” impredecibles entre agentes. 
Regla Backbone: si no está en /docs o en el código con ADR/README, “no existe” para el equipo.
2.2 Decisiones arquitectónicas (ADR)
Cada decisión grande (auth, RLS, tokens, grants temporales) lleva un ADR:
Contexto → Decisión → Alternativas → Consecuencias → Cómo revertir.
ADR obligatorio cuando un agente proponga un cambio transversal (db schema, auth flow, permisos).
2.3 Contrato de cambios
Toda tarea termina en PR pequeño y revisable:
1 tema = 1 PR
migraciones separadas si cambian schema + app
Prohibido “mega PR” generado por agente sin checkpoints.

3) Protocolo de conservación de contexto (Multi-Agent-Memory)
La regla del “Chesterton’s Fence”: Antes de eliminar o refactorizar código que no creaste tú (o que creaste en un prompt anterior), debes analizar y enunciar por qué ese código existía. No borres sin entender la dependencia.
Código Auto-Documentado: Los nombres de las variables y funciones deben ser tan descriptivos que no requieran comentarios (getUserById es mejor que getData).
Excepción: Usa comentarios explicativos solo para lógica de negocio compleja o decisiones no obvias (‘hack’ temporal)
Atomicidad en Cambios: Cada generación de código debe ser un cambio completo y funcional. No dejes funciones a medio escribir o “TODOs” críticos que rompan la compilación/ejecución.
4) UI/UX: Sistema de diseño atómico (Atomic Vibe)
Tokenización: Nunca uses ‘magic numbers’ o colores hardcodeados (ej: #FOO,12px). Usa siempre variables semánticas (ej: Colors.danger, Spacing.medium)
Objetivo: Mantener la “vibe” visual consistente, sin importar qué agente genere la vista.
Componentización Recursiva: Si un elemento de UI se usa más de una vez (o tienen mapas de 20 líneas de código visual), extraélo a un componente aislado inmediatamente.
Resiliencia visual: Todos los componentes deben manejar sus estados de borde: Loading, Error, Empty y Data Overflow (texto muy largo).
.5) Estándares de calidad genéricos (Clean Code)
S.O.L.I.D. Simplificado: 
S: una función/clase hace UNA sola cosa.
O: Abierto para extensión, cerrado para modificación (prefiere composición sobre herencia excesiva)
Early Return Pattern: Evita el “Arrow Code” (anidamiento excesivo de if/else). Verifica las condiciones negativas primero y retorna, dejando el “camino feliz” al final y plano.
Manejo de Errores Global: Nunca silencies un error. Si No puedes manejarlo localmente, propágalo hacia arriba hasta una capa que pueda informar al usuario.
6) Meta-instrucciones de auto-corrección (para agentes y humanos)
Antes de entregar el código final, ejecuta un simulación mental: “Si implemento esto, ¿ Rompo la arquitectura definida en el paso I? ¿ Estoy respetando los tokens de diseño del paso III?”. Si la respuesta es negativa, refactoriza antes de responder.