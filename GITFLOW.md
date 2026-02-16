# Git Flow - Spatial Iteration Engine

**Flujo simplificado y práctico** para desarrollo ágil. Menos ramas, más claridad.

## 🎯 Filosofía

- **Simplicidad sobre burocracia**: Solo las ramas necesarias
- **Desarrollo continuo**: Integración frecuente, deploys rápidos
- **Claridad**: Cada rama tiene un propósito claro y único

## 🌿 Ramas (Solo 3 tipos)

### 1. `main` - Producción
- **Propósito**: Código estable, listo para usar
- **Protección**: No commits directos, solo merges desde `develop`
- **Tags**: Versiones se etiquetan aquí (`v1.0.0`, `v1.1.0`)

### 2. `develop` - Integración
- **Propósito**: Rama de trabajo principal, integra todas las features
- **Protección**: Commits directos permitidos solo para cambios menores (docs, typos)
- **Flujo**: Features se mergean aquí antes de ir a `main`

### 3. `feature/*` - Trabajo en progreso
- **Propósito**: Desarrollo de nuevas funcionalidades o fixes
- **Origen**: Se crea desde `develop`
- **Destino**: Se mergea de vuelta a `develop`
- **Ejemplos**: 
  - `feature/cpp-filters`
  - `feature/notebook-preview`
  - `fix/memory-leak-buffer`

**No usamos**: `bugfix/*`, `hotfix/*`, `release/*` (demasiado complejo)

## 📝 Convenciones de Commits

### Formato (Conventional Commits)

```
<tipo>(<alcance>): <descripción corta>

<descripción detallada opcional>
```

### Tipos permitidos

| Tipo | Uso | Ejemplo |
|------|-----|---------|
| `feat` | Nueva funcionalidad | `feat(cpp): add blur filter` |
| `fix` | Corrección de bug | `fix(python): resolve memory leak` |
| `docs` | Solo documentación | `docs: update installation guide` |
| `refactor` | Refactor sin cambiar comportamiento | `refactor(engine): extract pipeline logic` |
| `perf` | Mejora de rendimiento | `perf(cpp): optimize matrix operations` |
| `test` | Tests | `test(python): add unit tests for filters` |
| `chore` | Mantenimiento (build, deps) | `chore: update CMakeLists.txt` |
| `mvp` | Avance en MVP específico | `mvp(02): complete cpp filter implementation` |

### Alcance (opcional pero recomendado)

- `cpp`, `python`, `docs`, `build`
- Módulos específicos: `cpp/filters`, `python/engine`, `python/perception`

### Ejemplos

```bash
feat(cpp/filters): add edge detection filter

Implementa detección de bordes usando Sobel operator con umbrales configurables.

Refs: MVP_02_CPP_FILTER

fix(python/engine): resolve frame buffer overflow

Corrige desbordamiento cuando se procesan más de 1000 fps.
Añade validación de tamaño máximo.

Fixes: #42

docs: update gitflow documentation

Simplifica flujo a solo main, develop y feature branches.
```

## 🔄 Flujo de Trabajo Diario

### Desarrollo de una Feature

```bash
# 1. Actualizar develop
git checkout develop
git pull origin develop

# 2. Crear rama de feature
git checkout -b feature/mi-feature

# 3. Trabajar y hacer commits
git add .
git commit -m "feat(scope): descripción"

# 4. Push de la rama
git push -u origin feature/mi-feature

# 5. Cuando está lista, mergear a develop
git checkout develop
git pull origin develop
git merge feature/mi-feature
git push origin develop

# 6. Eliminar rama local (opcional)
git branch -d feature/mi-feature
```

### Fixes Rápidos

Para bugs pequeños, puedes trabajar directamente en `develop`:

```bash
git checkout develop
git pull origin develop
# ... hacer cambios ...
git commit -m "fix(scope): descripción del fix"
git push origin develop
```

Para bugs más complejos, usa una rama `feature/`:

```bash
git checkout -b feature/fix-nombre-del-bug
# ... trabajar ...
# Merge a develop como cualquier feature
```

### Release (cuando sea necesario)

```bash
# 1. Desde develop, crear tag
git checkout develop
git pull origin develop

# 2. Merge a main
git checkout main
git pull origin main
git merge develop
git tag v1.2.0
git push origin main --tags

# 3. Volver a develop
git checkout develop
```

**Nota**: No necesitas rama `release/*` a menos que tengas múltiples versiones en producción simultáneamente.

## 📋 Changelog

### Actualización Obligatoria

Cada cambio que afecte funcionalidad visible debe actualizar `CHANGELOG.md`:

1. **Ubicación**: Sección `[Unreleased]` al inicio
2. **Formato**: Categorías `Added`, `Changed`, `Fixed`, `Removed`
3. **Cuándo**: En el mismo commit o en el merge a `develop`

### Ejemplo

```markdown
## [Unreleased]

### Added
- `feat(cpp)`: Implementación de filtro de detección de bordes
- `feat(python)`: Soporte para múltiples cámaras simultáneas

### Changed
- `refactor(python)`: Reorganización de módulos de percepción

### Fixed
- `fix(cpp)`: Corrección de memory leak en filtros
```

### Al hacer Release

Mover `[Unreleased]` a una nueva sección con la versión:

```markdown
## [1.2.0] - 2024-12-19

### Added
- `feat(cpp)`: Implementación de filtro de detección de bordes
...

## [Unreleased]
```

## ✅ Buenas Prácticas

### Antes de Commit

- [ ] Código compila sin errores
- [ ] Tests pasan (si existen)
- [ ] Linter/formatting aplicado
- [ ] `CHANGELOG.md` actualizado (si aplica)

### Antes de Push

- [ ] Commits siguen formato Conventional Commits
- [ ] Mensajes son claros y descriptivos
- [ ] Branch está actualizada con `develop` (`git pull --rebase origin develop`)

### Antes de Merge a develop

- [ ] Código revisado (self-review mínimo)
- [ ] No hay conflictos
- [ ] `CHANGELOG.md` actualizado
- [ ] Build pasa

### Respeto a MVPs

- **No trabajar fuera de MVPs**: Solo implementar lo definido en los MVPs canónicos
- **Orden obligatorio**: Respetar el orden MVP_01 → MVP_02 → MVP_03 → MVP_04
- **Si algo rompe un MVP**: Detener desarrollo hasta corregir

### Estructura de Commits

- **Un commit = un cambio lógico**: No mezclar múltiples cambios no relacionados
- **Commits pequeños y frecuentes**: Facilita revisión y rollback
- **Commits atómicos**: Cada commit debe dejar el proyecto en un estado funcional

## 🚫 Qué NO hacer

1. **No commits directos a `main`** (excepto merges desde `develop`)
2. **No `git push --force` a `main` o `develop`** (salvo acuerdo explícito)
3. **No mezclar múltiples features en una rama**
4. **No commits de "WIP" o "fix typo" sin contexto**
5. **No ignorar el CHANGELOG** para cambios relevantes

## 🔍 Alcance de Cambios

### Módulos del Proyecto

- **`cpp/`**: Código C++ (filtros, render, percepción)
- **`python/`**: Código Python (engine, perception, style)
- **`docs/`**: Documentación
- **`rules/`**: Reglas y MVPs
- **`scripts/`**: Scripts de utilidad
- **`data/`**: Datos y assets
- **`onnx_models/`**: Modelos ONNX

### Ejemplos de Alcance

```
feat(cpp/filters): add blur filter
fix(python/engine): resolve pipeline deadlock
docs(architecture): update integration guide
chore(build): update CMake version
mvp(02): complete cpp filter implementation
```

## 📊 Comparación con Otros Flujos

| Aspecto | Gitflow Tradicional | **Este Flujo (Simplificado)** | GitHub Flow |
|---------|---------------------|-------------------------------|-------------|
| Ramas principales | main, develop | **main, develop** | main |
| Ramas de feature | feature/* | **feature/*** | feature/* |
| Ramas de release | release/* | **No (merge directo)** | No |
| Ramas de hotfix | hotfix/* | **No (usa feature/)** | No |
| Complejidad | Alta | **Media** | Baja |
| Ideal para | Proyectos grandes | **Equipos pequeños/medianos** | Startups |

## 📚 Referencias

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- MVPs del proyecto: `rules/MVP_INDEX.md`

---

**Última actualización**: 2024-12-19  
**Versión del documento**: 2.0.0 (Simplificado)
