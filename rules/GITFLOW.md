# Git Flow — Spatial Iteration Engine

Este documento define el flujo de trabajo con Git que el equipo respeta a partir de su adopción.
Cualquier cambio que afecte ramas, commits o releases debe seguir estas reglas.

---

## 1. Ramas

| Rama | Propósito | Protección |
|------|-----------|------------|
| `main` | Código estable listo para producción. Solo integración vía merge desde `develop` o `release/*`. | No commit directo. Solo merge de `develop` o de `release/*` (con tag). |
| `develop` | Integración de features y fixes. Rama de trabajo principal. | Commits y merges de `feature/*`, `fix/*`, `docs/*`. |
| `feature/*` | Nueva funcionalidad acotada (ej. `feature/notebook-ia-panel`). | Se crea desde `develop`, se mergea de vuelta a `develop`. |
| `fix/*` | Corrección de bugs (ej. `fix/perception-empty-array`). | Se crea desde `develop`, se mergea a `develop`. |
| `docs/*` | Solo documentación o reglas (ej. `docs/gitflow`). | Opcional: puede ir directo a `develop` o rama corta. |
| `release/*` | Preparación de una versión (changelog, versión). Solo si se hace release formal. | Se crea desde `develop`, merge a `main` y a `develop`. |

**Regla:** Todo trabajo nuevo se hace en una rama derivada de `develop` (salvo hotfix en producción, que no aplica hasta tener releases formales).

---

## 2. Alcance de cada cambio

- **Un branch = un alcance lógico** (una feature, un fix, una doc).
- **Un commit = un cambio atómico** dentro de ese alcance (una idea que se pueda revertir o describir en una línea).
- **Evitar:** mezclar en un mismo commit cambios de código, docs y formato; o varias features no relacionadas.

---

## 3. Formato de commits (Conventional Commits)

Formato obligatorio para mensajes de commit:

```
<tipo>(<alcance opcional>): <descripción corta>

[Cuerpo opcional: qué y por qué, no cómo.]
```

**Tipos permitidos:**

| Tipo | Uso |
|------|-----|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Solo documentación |
| `refactor` | Refactor sin cambiar comportamiento observable |
| `perf` | Mejora de rendimiento |
| `test` | Añadir o cambiar tests |
| `build` | CMake, scripts de build, dependencias |
| `chore` | Tareas de mantenimiento (ej. actualizar .gitignore) |

**Ejemplos:**

- `feat(notebook): add IA tab with face/hands/pose detection and overlay`
- `fix(perception): create numpy array with vector shape for pybind11`
- `docs(rules): add GITFLOW and CHANGELOG policy`

---

## 4. Changelog

- El archivo **`CHANGELOG.md`** en la raíz del repo es la fuente de verdad de cambios por versión.
- Formato: [Keep a Changelog](https://keepachangelog.com/) (es decir: `Added`, `Changed`, `Fixed`, etc.).
- **Regla:** Todo merge a `develop` que sea una feature o fix relevante debe tener su línea en `CHANGELOG.md` bajo `[Unreleased]` (o bajo la versión si es release).
- Quién hace el merge (o el autor del PR) es responsable de actualizar el changelog en el mismo commit o en el merge.

**Estructura mínima:**

```markdown
# Changelog

## [Unreleased]
### Added
- Descripción de lo nuevo.
### Fixed
- Descripción del fix.

## [0.1.0] - YYYY-MM-DD
...
```

---

## 5. Buenas prácticas

1. **Pull antes de push:** `git pull --rebase origin develop` (o la rama en la que trabajes) antes de subir.
2. **Commits pequeños y frecuentes:** más fácil de revisar y revertir.
3. **No subir a main/develop código roto:** el build y los tests relevantes deben pasar antes del merge.
4. **Tags en main:** las versiones se etiquetan en `main` (ej. `v0.2.0`) tras un merge de `release/*` o de `develop` si no hay rama release.
5. **Descripción en merge:** al mergear a `develop` (o a `main`), el merge commit puede resumir el alcance (o usar el título del PR/branch).
6. **No reescribir historia en ramas compartidas:** no `git push --force` a `develop` ni `main` salvo acuerdo explícito.

---

## 6. Resumen del flujo diario

1. Actualizar local: `git checkout develop && git pull --rebase origin develop`
2. Crear rama: `git checkout -b feature/mi-feature`
3. Trabajar, commits con formato conventional
4. Actualizar `CHANGELOG.md` bajo `[Unreleased]` si aplica
5. Push: `git push -u origin feature/mi-feature`
6. Merge a `develop` (PR o directo según política del equipo)
7. Para release: rama `release/v0.x.0` desde `develop`, actualizar versión y changelog, merge a `main` y a `develop`, tag `v0.x.0` en `main`

---

## 7. Referencia rápida

- **Ramas:** `main` (estable), `develop` (integración), `feature/*`, `fix/*`, `release/*`
- **Commits:** `tipo(alcance): descripción`
- **Changelog:** siempre actualizar en `CHANGELOG.md` para cambios que afecten a usuarios o builds
- **Tags:** solo en `main`, formato `v0.x.0`

