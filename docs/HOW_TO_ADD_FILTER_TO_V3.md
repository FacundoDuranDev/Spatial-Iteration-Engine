# Cómo integrar un filtro nuevo al dashboard v3

Receta paso a paso para enchufar cualquier filtro existente (o nuevo)
al dashboard mobile v3 sin tocar `bridge.py`, `ws.py` ni el frontend.
Toda la integración es **declarativa en `registry.py`**.

> Pre-requisito: el filtro ya existe como clase Python en
> `adapters/processors/filters/`, implementa el `Filter` protocol
> (`apply(frame, ctx) -> frame`) y tiene un atributo público
> `enabled: bool`. Si no, primero resolvelo siguiendo
> `rules/PIPELINE_EXTENSION_RULES.md`.

---

## TL;DR — checklist de 5 puntos

1. **Importá** la clase en `registry.py`.
2. **Agregá un dict** a `FILTERS` con `id`, `name`, `cat`, `wip:False`,
   `factory`, `params`.
3. **Para cada parámetro** definí: `id`, `kind`, `default`, `label`,
   `apply(filter, value)`, y los rangos según `kind`.
4. **Espejá** el mismo dict en `static/app.js → FILTERS` (el frontend
   lo necesita para renderizar antes del primer state push). IDs y
   tipos deben coincidir bit a bit.
5. **Validá**: arrancá `run_dashboard_mobile_v3.py`, drill al filtro,
   movele un control, mirá la ventana de cv2.

---

## Paso 1 · Importar la clase

`python/ascii_stream_engine/adapters/outputs/web_dashboard/registry.py`:

```python
from ascii_stream_engine.adapters.processors.filters import (
    BloomFilter,
    CppBrightnessContrastFilter,
    CppTemporalScanFilter,
    MiNuevoFilter,            # ← acá
)
```

## Paso 2 · Agregar el dict a `FILTERS`

```python
{
    "id":      "mi_filtro",        # snake_case, único, ≤ 16 chars
    "name":    "Mi Filtro",        # mostrar en español
    "cat":     "DISTORT",          # uno de: DISTORT / COLOR / GLITCH / STYLIZE
    "wip":     False,              # True = stub visible pero no operable
    "factory": lambda: MiNuevoFilter(param_a=0.5, param_b=10),
    "params": [
        # ver paso 3
    ],
},
```

- `id` es el handle del WebSocket: el cliente manda
  `{"op":"toggle_filter", "filter":"mi_filtro", "on":true}`.
- `factory` se llama UNA vez, la primera vez que el usuario toca el
  toggle. La instancia queda guardada y se reutiliza.
- Si `cat` no es uno de los 4 actuales, el filtro NO aparece en la UI
  (y la consola no avisa). Si querés una nueva categoría, agregala
  también a `CATEGORIES` y al espejo en `app.js`.

## Paso 3 · Declarar cada parámetro

Cada `param` necesita estos campos (mínimo):

| campo | obligatorio | descripción |
|---|---|---|
| `id` | sí | snake_case único dentro del filtro |
| `kind` | sí | uno de: `slider`, `stepper`, `dial`, `angle`, `select`, `switch` |
| `default` | sí | valor inicial |
| `label` | sí | texto en español, mostrar en UI |
| `apply` | sí | `lambda f, v: …` que aplica el cambio en la instancia |

Y según el `kind`:

| `kind` | extras | UI |
|---|---|---|
| `slider` | `min`, `max`, `step` (float ok) | track horizontal con thumb cyan |
| `stepper` | `min`, `max`, `step` (int) | botones − valor + |
| `dial` / `angle` | `min`, `max`, `step` (típico 0–360) | rueda circular |
| `select` | `options: [str, …]` | pills segmentadas |
| `switch` | (ninguno) | toggle on/off |

### El callback `apply` — atención al storage

El callback recibe la instancia del filtro y el valor ya **clamped**
por el server. Lo único que tenés que hacer es escribir en el
atributo correcto. **Ojo**: muchos filtros del repo guardan estado
en atributos privados con leading underscore. Hacer
`setattr(f, "intensity", v)` cuando la instancia espera `_intensity`
crea un atributo público fantasma y el `apply()` del filtro nunca lo
lee → bug silencioso.

Ejemplos correctos:

```python
# TemporalScan: tiene @property real
{"id": "angle", "kind": "angle", "min": 0.0, "max": 360.0, "step": 1.0,
 "default": 0.0, "label": "Ángulo de scan",
 "apply": lambda f, v: setattr(f, "angle_deg", float(v))},

# Bloom: usa atributo privado, hay que escribir el privado
{"id": "intensity", "kind": "slider", "min": 0.0, "max": 1.0, "step": 0.05,
 "default": 0.6, "label": "Intensidad",
 "apply": lambda f, v: setattr(f, "_intensity", float(v))},

# BC: idem
{"id": "brightness", "kind": "slider", "min": -100, "max": 100, "step": 5,
 "default": 0, "label": "Brillo",
 "apply": lambda f, v: setattr(f, "_brightness_delta", int(v))},

# Select: una de N opciones
{"id": "curve", "kind": "select", "options": ["linear", "ease"],
 "default": "linear", "label": "Curva",
 "apply": lambda f, v: setattr(f, "curve", v)},
```

**Cómo saber qué atributo escribir**: abrí la clase del filtro y
buscá su `__init__` y `apply()`. Lo que `apply()` LEE es lo que tu
callback debe ESCRIBIR. Si `apply()` lee `self._intensity`, escribí
en `_intensity`, no en `intensity`.

### Cómo se lee el valor para el snapshot

`bridge.py → _read_one_param` mapea `(filter_id, param_id)` al
atributo real. Si agregaste un filtro nuevo, agregá ahí un branch:

```python
elif fid == "mi_filtro":
    if pid == "fuerza":
        return float(getattr(inst, "_strength", fallback))
```

Si no lo agregás, el valor vivo no se ve en la UI (siempre muestra
el default), pero el filtro sí recibe los cambios igual. Es un bug
cosmético, no funcional.

## Paso 4 · Espejar en el frontend

`python/ascii_stream_engine/adapters/outputs/web_dashboard/static/app.js`,
buscá el const `FILTERS = [` y agregá la misma estructura:

```js
{
  id: "mi_filtro",
  name: "Mi Filtro",
  cat: "DISTORT",
  wip: false,
  params: [
    { id: "fuerza", kind: "slider", min: 0.0, max: 10.0, step: 0.5,
      default: 3.0, label: "Fuerza" },
  ],
},
```

**No** copies el `factory` ni el `apply` — el frontend solo necesita
saber rangos y labels para renderizar. Los valores los lee del
snapshot del servidor.

## Paso 5 · Validar

```bash
conda activate spatial-iteration-engine
git checkout feat/web-dashboard-v3
PYTHONPATH=python:cpp/build python run_dashboard_mobile_v3.py
```

En el celular o `http://127.0.0.1:7861/`:

1. La categoría a la que asignaste el filtro debería decir
   "X activos / N total" donde N subió en 1.
2. Tap la categoría → tu filtro aparece como una row.
3. Tap el chevron → entrás a detail.
4. Tap "Activo" → instancia se crea, se agrega al pipeline.
5. Si el engine está corriendo, ya deberías ver el efecto en la
   ventana de cv2.
6. Movés un control → cv2 cambia en < 100 ms.

Si el slider mueve pero cv2 no cambia → el `apply` está escribiendo
el atributo equivocado (volvé al paso 3).

Si el filtro nunca aparece → mismatch entre el `cat` del registry y
las CATEGORIES, o falta el espejo en `app.js`.

Si el toggle dispara error `wip_filter` → tenés `wip: True`
todavía.

## Anti-checklist (cosas a evitar)

- ❌ Modificar `bridge.py`, `ws.py`, `protocol.py` para enchufar un
  filtro normal. La capa de transport es genérica.
- ❌ Agregar la clase del filtro al `registry.py` antes de que
  funcione standalone (probala primero en `tests/` o `notebook_api`).
- ❌ Inventar un `kind` nuevo (ej. `color_picker`) sin agregar el
  binder vanilla en `app.js`. Si necesitás un nuevo widget, sumalo
  primero al frontend.
- ❌ Usar `apply: lambda f, v: f.set_param(v)` si el filtro no tiene
  ese método. La capa de transporte no garantiza re-entry-safety.
- ❌ Olvidar el espejo en `app.js` (la UI no muestra el filtro hasta
  que esté).

## Promover un WIP a wired

Hoy `chroma` e `invert` están como WIP. Para promover uno:

1. En `registry.py`, cambiar `wip: True → False`, agregar `factory`,
   y la lista `params`.
2. En `bridge.py → _read_one_param`, agregar el branch del filtro.
3. En `app.js → FILTERS`, mismo cambio (`wip: false`, params).
4. Validar.

Eso es todo.

---

## Referencias

- `python/ascii_stream_engine/adapters/outputs/web_dashboard/registry.py` — fuente de verdad backend
- `python/ascii_stream_engine/adapters/outputs/web_dashboard/static/app.js` — espejo frontend (buscar `const FILTERS`)
- `python/ascii_stream_engine/adapters/outputs/web_dashboard/bridge.py → _read_one_param` — mapping de atributos vivos
- `.claude/scratch/ws_protocol.md` — contrato WS (no necesita tocarse)
- `rules/PIPELINE_EXTENSION_RULES.md` — cómo escribir el filtro en sí
- `docs/decisions/web_dashboard.md` — por qué v3 existe
