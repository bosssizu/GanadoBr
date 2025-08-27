# GanadoBravo v39k — stronger condition gating

**Cambios clave**
- Si **BCS ≤ 2.6**:
  - Baja **Conformación** y **Lomo** automáticamente (con observaciones).
  - **Angulación costillar** se ajusta a 4.0–6.0 cuando hay intercostales visibles.
  - **Aplomos** pesa **la mitad** (0.5x) para reducir sobreconfianza lateral.
  - **Sin bono posterior** si BCS < 3.4.
- Promedia el puntaje **ponderado** por métricas (muestra pesos en `debug.weights`).

Mantiene: salud itemizada, raza (si la activas), timeouts y watchdog.

Deploy: `bash start.sh` ; variables como en v39j.
