# Git Flow - Spatial Iteration Engine

Este documento define el flujo de trabajo Git que se seguirá a partir de ahora en el proyecto Spatial Iteration Engine.

## 📋 Tabla de Contenidos

- [Ramas](#ramas)
- [Tipos de Cambios](#tipos-de-cambios)
- [Proceso de Desarrollo](#proceso-de-desarrollo)
- [Convenciones de Commits](#convenciones-de-commits)
- [Changelog](#changelog)
- [Releases](#releases)
- [Buenas Prácticas](#buenas-prácticas)

## 🌿 Ramas

### Ramas Principales

- **`main`**: Rama de producción. Solo contiene código estable, probado y listo para release.
- **`develop`**: Rama de desarrollo. Integra todas las features y correcciones antes de mergear a `main`.

### Ramas de Soporte

- **`feature/*`**: Nuevas funcionalidades. Se crean desde `develop` y se mergean de vuelta a `develop`.
- **`bugfix/*`**: Correcciones de bugs. Se crean desde `develop` o `main` (dependiendo de la urgencia).
- **`hotfix/*`**: Correcciones urgentes en producción. Se crean desde `main` y se mergean a `main` y `develop`.
- **`release/*`**: Preparación de releases. Se crean desde `develop` y se mergean a `main` y `develop`.

## 🏷️ Tipos de Cambios

Cada cambio debe clasificarse según su alcance:

### `feat`: Nueva funcionalidad
- Añade una nueva característica al sistema
- Ejemplo: `feat(cpp): add brightness filter implementation`

### `fix`: Corrección de bug
- Corrige un error en el código existente
- Ejemplo: `fix(python): resolve memory leak in frame buffer`

### `docs`: Documentación
- Cambios solo en documentación
- Ejemplo: `docs: update installation guide`

### `style`: Formato de código
- Cambios que no afectan el significado del código (espacios, formato, etc.)
- Ejemplo: `style(cpp): fix indentation in filters`

### `refactor`: Refactorización
- Cambios que mejoran el código sin cambiar funcionalidad
- Ejemplo: `refactor(python): extract common pipeline logic`

### `perf`: Mejoras de rendimiento
- Optimizaciones que mejoran el rendimiento
- Ejemplo: `perf(cpp): optimize matrix operations in filters`

### `test`: Tests
- Añade o modifica tests
- Ejemplo: `test(python): add unit tests for perception module`

### `chore`: Tareas de mantenimiento
- Cambios en build, dependencias, configuración
- Ejemplo: `chore: update CMakeLists.txt dependencies`

### `mvp`: Cambios relacionados con MVPs
- Implementación o avance en un MVP específico
- Ejemplo: `mvp(03): implement face landmarks detection`

## 🔄 Proceso de Desarrollo

### 1. Crear una Feature

```bash
# Desde develop
git checkout develop
git pull origin develop
git checkout -b feature/nombre-de-la-feature

# Trabajar en la feature
# ... hacer commits ...

# Push de la rama
git push origin feature/nombre-de-la-feature
```

### 2. Crear un Bugfix

```bash
# Desde develop (o main si es crítico)
git checkout develop
git pull origin develop
git checkout -b bugfix/descripcion-del-bug

# Trabajar en el bugfix
# ... hacer commits ...

# Push de la rama
git push origin bugfix/descripcion-del-bug
```

### 3. Crear un Hotfix

```bash
# Desde main
git checkout main
git pull origin main
git checkout -b hotfix/descripcion-urgente

# Trabajar en el hotfix
# ... hacer commits ...

# Merge a main y develop
git checkout main
git merge hotfix/descripcion-urgente
git checkout develop
git merge hotfix/descripcion-urgente
```

### 4. Crear un Release

```bash
# Desde develop
git checkout develop
git pull origin develop
git checkout -b release/v1.2.0

# Preparar release (actualizar versiones, changelog, etc.)
# ... hacer commits ...

# Merge a main y develop
git checkout main
git merge release/v1.2.0
git tag v1.2.0
git checkout develop
git merge release/v1.2.0
```

## 📝 Convenciones de Commits

### Formato

```
<tipo>(<alcance>): <descripción corta>

<descripción detallada opcional>

<referencias opcionales>
```

### Ejemplos

```
feat(cpp): add edge detection filter

Implementa el filtro de detección de bordes usando Sobel operator
con soporte para umbrales configurables.

Refs: MVP_02_CPP_FILTER
```

```
fix(python): resolve frame buffer overflow

Corrige el desbordamiento del buffer cuando se procesan más de
1000 frames por segundo. Añade validación de tamaño máximo.

Fixes: #42
```

```
docs: update gitflow documentation

Añade sección sobre releases y mejores prácticas de branching.
```

### Reglas

1. **Tipo obligatorio**: Siempre incluir el tipo de cambio
2. **Alcance opcional**: Especificar módulo afectado (cpp, python, docs, etc.)
3. **Descripción**: Máximo 72 caracteres, imperativo, sin punto final
4. **Cuerpo opcional**: Explicar el qué y el por qué, no el cómo
5. **Referencias**: Incluir issues, PRs, o MVPs relacionados

## 📋 Changelog

### Actualización Obligatoria

Cada commit que afecte funcionalidad visible debe actualizar `CHANGELOG.md`:

1. **Ubicación**: En la sección `[Unreleased]` al inicio del archivo
2. **Formato**: Seguir el formato establecido en `CHANGELOG.md`
3. **Categorías**: Usar las mismas categorías que los tipos de commits

### Ejemplo de Entrada

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

## 🚀 Releases

### Versionado Semántico

Seguimos [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`

- **MAJOR**: Cambios incompatibles con versiones anteriores
- **MINOR**: Nueva funcionalidad compatible hacia atrás
- **PATCH**: Correcciones de bugs compatibles

### Proceso de Release

1. Crear rama `release/vX.Y.Z` desde `develop`
2. Actualizar versiones en código y documentación
3. Actualizar `CHANGELOG.md` moviendo `[Unreleased]` a `[vX.Y.Z]`
4. Crear PR para revisión
5. Merge a `main` y crear tag `vX.Y.Z`
6. Merge de vuelta a `develop`
7. Publicar release en GitHub (si aplica)

## ✅ Buenas Prácticas

### Antes de Commit

- [ ] Código compila sin errores
- [ ] Tests pasan (si existen)
- [ ] Linter/formatting aplicado
- [ ] `CHANGELOG.md` actualizado (si aplica)
- [ ] Documentación actualizada (si aplica)

### Antes de Push

- [ ] Commits siguen el formato establecido
- [ ] Mensajes de commit son claros y descriptivos
- [ ] No hay commits de "WIP" o "fix typo" sin contexto
- [ ] Branch está actualizada con la rama base

### Antes de Merge

- [ ] Código revisado (self-review mínimo)
- [ ] Tests pasan en CI (si existe)
- [ ] No hay conflictos con la rama base
- [ ] `CHANGELOG.md` está actualizado
- [ ] Documentación está actualizada

### Respeto a MVPs

- **No trabajar fuera de MVPs**: Solo implementar lo definido en los MVPs canónicos
- **Orden obligatorio**: Respetar el orden MVP_01 → MVP_02 → MVP_03 → MVP_04
- **Si algo rompe un MVP**: Detener desarrollo hasta corregir

### Estructura de Commits

- **Un commit = un cambio lógico**: No mezclar múltiples cambios no relacionados
- **Commits pequeños y frecuentes**: Facilita revisión y rollback
- **Commits atómicos**: Cada commit debe dejar el proyecto en un estado funcional

### Workflow Recomendado

```bash
# Trabajo diario
git checkout develop
git pull origin develop
git checkout -b feature/mi-feature

# Desarrollo iterativo
# ... hacer cambios ...
git add .
git commit -m "feat(scope): descripción"
git push origin feature/mi-feature

# Cuando la feature está lista
git checkout develop
git pull origin develop
git merge feature/mi-feature
git push origin develop
```

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

## 📚 Referencias

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
- MVPs del proyecto: `rules/MVP_INDEX.md`

---

**Última actualización**: 2024-12-19
**Versión del documento**: 1.0.0

