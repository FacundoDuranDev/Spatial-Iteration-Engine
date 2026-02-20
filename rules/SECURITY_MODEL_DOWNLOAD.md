# Reglas de Seguridad — Descarga de Modelos de IA

**Autoridad**: Este documento define las políticas obligatorias para descargar, validar y usar modelos de IA (ONNX, TFLite, etc.) en el proyecto. Cualquier script o proceso que descargue modelos debe cumplir estas reglas.

**Última actualización**: 2025-02-16

---

## 1. Fuentes Permitidas (Whitelist)

Solo se permiten descargas desde las siguientes fuentes:

### 1.1 Fuentes de Alta Confiabilidad (Nivel 1)

| Fuente | Dominio | Verificación Requerida |
|--------|---------|------------------------|
| **HuggingFace** | `huggingface.co` | ✅ Checksum SHA256 (si disponible) |
| **ONNX Model Zoo** | `github.com/onnx/models` | ✅ Verificación de firma Git |
| **Google Research / MediaPipe** | `github.com/google/mediapipe` | ✅ Verificación de firma Git |
| **Microsoft Research** | `github.com/microsoft` | ✅ Verificación de firma Git |
| **Meta Research** | `github.com/facebookresearch` | ✅ Verificación de firma Git |

### 1.2 Fuentes de Confiabilidad Media (Nivel 2)

| Fuente | Dominio | Verificación Requerida |
|--------|---------|------------------------|
| **PyTorch Hub** | `pytorch.org` | ✅ Checksum SHA256 obligatorio |
| **TensorFlow Hub** | `tensorflow.org` | ✅ Checksum SHA256 obligatorio |
| **Repositorios académicos** | Dominios `.edu` verificados | ✅ Verificación de autor + checksum |

### 1.3 Fuentes Prohibidas

- ❌ URLs acortadas (bit.ly, tinyurl, etc.)
- ❌ Sitios de alojamiento de archivos genéricos sin verificación (MediaFire, etc.)
- ❌ Repositorios sin mantenimiento activo (>6 meses sin commits)
- ❌ Fuentes sin documentación pública del modelo
- ❌ Cualquier fuente no listada explícitamente como permitida

**Regla**: Si una fuente no está en la whitelist, se debe solicitar aprobación explícita antes de descargar.

---

## 2. Verificaciones Obligatorias

Todo modelo descargado **DEBE** pasar las siguientes verificaciones antes de ser usado:

### 2.1 Verificación de Integridad (Checksum)

**Obligatorio**: Verificar checksum SHA256 del archivo descargado.

```bash
# Formato esperado: archivo.sha256 contiene "SHA256_HASH  filename"
sha256sum -c archivo.sha256
```

**Si no hay checksum disponible**:
- ⚠️ **ADVERTENCIA**: El modelo no debe usarse en producción
- ✅ **Permitido solo para desarrollo/testing** con aprobación explícita
- 📝 **Documentar**: Registrar en `SECURITY_AUDIT.md` que no hay checksum

### 2.2 Verificación de Formato

**Obligatorio**: Validar que el archivo es del formato esperado.

**Para ONNX**:
```bash
# Magic bytes: debe comenzar con protobuf ONNX
python3 -c "import onnx; onnx.checker.check_model('model.onnx')"
```

**Para TFLite**:
```bash
# Magic bytes: "TFL3" o formato FlatBuffers válido
file model.tflite | grep -q "TFLite"
```

**Si el formato no coincide**:
- ❌ **RECHAZAR**: Eliminar el archivo inmediatamente
- 📝 **Registrar**: Error en logs de seguridad

### 2.3 Verificación de Permisos

**Obligatorio**: Asegurar que el archivo NO es ejecutable.

```bash
# Permisos correctos: 644 (rw-r--r--)
chmod 644 model.onnx
# Verificar que NO es ejecutable
[ ! -x model.onnx ] || exit 1
```

### 2.4 Verificación de Tamaño

**Obligatorio**: Validar que el tamaño del archivo es razonable.

- **Mínimo**: 1 KB (archivos muy pequeños pueden ser corruptos o maliciosos)
- **Máximo**: 500 MB (archivos muy grandes requieren aprobación especial)
- **Tamaño esperado**: Documentar el tamaño esperado en el script de descarga

```bash
# Ejemplo de validación
MIN_SIZE=1024  # 1 KB
MAX_SIZE=524288000  # 500 MB
FILE_SIZE=$(stat -f%z model.onnx 2>/dev/null || stat -c%s model.onnx)
if [ "$FILE_SIZE" -lt "$MIN_SIZE" ] || [ "$FILE_SIZE" -gt "$MAX_SIZE" ]; then
  echo "ERROR: Tamaño de archivo sospechoso: $FILE_SIZE bytes"
  exit 1
fi
```

### 2.5 Escaneo de Strings Sospechosos

**Obligatorio**: Buscar strings que indiquen código ejecutable malicioso.

**Strings prohibidos**:
- `eval(`, `exec(`, `__import__`
- `subprocess`, `os.system`, `popen`
- `#!/bin/sh`, `#!/bin/bash` (shebang en archivos binarios)
- URLs de descarga automática
- Comandos de shell peligrosos

```bash
# Verificación básica
SUSPICIOUS_STRINGS=("eval(" "exec(" "__import__" "subprocess" "os.system")
for str in "${SUSPICIOUS_STRINGS[@]}"; do
  if strings model.onnx | grep -q "$str"; then
    echo "ERROR: String sospechoso encontrado: $str"
    exit 1
  fi
done
```

---

## 3. Proceso de Descarga Segura

### 3.1 Flujo Obligatorio

```
1. Verificar fuente en whitelist
   ↓
2. Descargar a ubicación temporal
   ↓
3. Verificar checksum (si disponible)
   ↓
4. Verificar formato de archivo
   ↓
5. Verificar permisos (no ejecutable)
   ↓
6. Verificar tamaño
   ↓
7. Escanear strings sospechosos
   ↓
8. Mover a ubicación final
   ↓
9. Registrar en SECURITY_AUDIT.md
```

### 3.2 Ubicaciones de Archivos

- **Temporal**: `onnx_models/.tmp/` (se limpia después de verificación)
- **Final**: `onnx_models/mediapipe/` (solo después de pasar todas las verificaciones)
- **Auditoría**: `SECURITY_AUDIT.md` (registro de todos los modelos descargados)

### 3.3 Manejo de Errores

- **Si cualquier verificación falla**: Eliminar archivo inmediatamente
- **Registrar error**: En `SECURITY_AUDIT.md` con timestamp
- **No continuar**: El script debe fallar con código de salida != 0

---

## 4. Documentación y Auditoría

### 4.1 Registro Obligatorio

Cada modelo descargado **DEBE** ser registrado en `SECURITY_AUDIT.md` con:

- ✅ **Fecha y hora de descarga**
- ✅ **URL de origen**
- ✅ **Checksum SHA256** (si disponible)
- ✅ **Tamaño del archivo**
- ✅ **Fuente verificada** (whitelist)
- ✅ **Resultado de todas las verificaciones**
- ✅ **Firma del auditor** (quien descargó/verificó)

### 4.2 Revisión Periódica

- **Frecuencia**: Cada 3 meses
- **Acción**: Revisar todos los modelos en `onnx_models/`
- **Verificar**: Que siguen cumpliendo las reglas actuales
- **Actualizar**: `SECURITY_AUDIT.md` con fecha de revisión

---

## 5. Excepciones y Aprobaciones

### 5.1 Proceso de Excepción

Si necesitas descargar desde una fuente no whitelisted:

1. **Documentar**: Razón técnica en issue o PR
2. **Obtener aprobación**: De al menos 2 mantenedores
3. **Actualizar whitelist**: Si la fuente es confiable a largo plazo
4. **Verificaciones adicionales**: Aplicar todas las verificaciones + revisión manual

### 5.2 Modelos para Desarrollo

Para modelos usados **solo en desarrollo/testing**:

- ✅ **Permitido**: Sin checksum si está documentado
- ⚠️ **Restricción**: NO debe usarse en producción
- 📝 **Marcar**: En `SECURITY_AUDIT.md` como "DEV ONLY"

---

## 6. Implementación en Scripts

### 6.1 Template de Script Seguro

Todos los scripts de descarga deben seguir este template:

```bash
#!/usr/bin/env bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# 1. Verificar fuente
SOURCE_URL="$1"
if ! validate_source "$SOURCE_URL"; then
  echo "ERROR: Fuente no permitida: $SOURCE_URL"
  exit 1
fi

# 2. Descargar a temporal
TEMP_FILE=$(mktemp)
download_to_temp "$SOURCE_URL" "$TEMP_FILE"

# 3. Verificar checksum (si disponible)
if [ -f "$EXPECTED_CHECKSUM_FILE" ]; then
  verify_checksum "$TEMP_FILE" "$EXPECTED_CHECKSUM_FILE" || exit 1
fi

# 4. Verificar formato
verify_format "$TEMP_FILE" "onnx" || exit 1

# 5. Verificar permisos
chmod 644 "$TEMP_FILE"
verify_not_executable "$TEMP_FILE" || exit 1

# 6. Verificar tamaño
verify_size "$TEMP_FILE" "$MIN_SIZE" "$MAX_SIZE" || exit 1

# 7. Escanear strings
scan_suspicious_strings "$TEMP_FILE" || exit 1

# 8. Mover a final
mv "$TEMP_FILE" "$FINAL_LOCATION"

# 9. Registrar auditoría
log_to_audit "$FINAL_LOCATION" "$SOURCE_URL"
```

### 6.2 Funciones Requeridas

Cada script debe implementar (o importar) estas funciones:

- `validate_source(url)`: Verificar whitelist
- `verify_checksum(file, checksum_file)`: Verificar SHA256
- `verify_format(file, expected_format)`: Validar formato
- `verify_not_executable(file)`: Asegurar permisos correctos
- `verify_size(file, min, max)`: Validar tamaño
- `scan_suspicious_strings(file)`: Buscar strings maliciosos
- `log_to_audit(file, source)`: Registrar en SECURITY_AUDIT.md

---

## 7. Cumplimiento y Sanciones

### 7.1 Verificación de Cumplimiento

- **Pre-commit hook**: Verificar que modelos nuevos pasan todas las verificaciones
- **CI/CD**: Ejecutar auditoría automática en cada PR
- **Revisión manual**: Para modelos de fuentes nuevas

### 7.2 Si se Violan las Reglas

- **Primera vez**: Advertencia + corrección requerida
- **Reincidencia**: Bloqueo temporal de commits que afecten modelos
- **Crítico**: Si se introduce modelo malicioso, revertir inmediatamente

---

## 8. Referencias y Estándares

Este documento sigue las mejores prácticas de:

- **OWASP ML Security**: Modelo de seguridad para ML
- **NIST Cybersecurity Framework**: Gestión de riesgos
- **GitHub Security Best Practices**: Verificación de integridad
- **ONNX Runtime Security**: Guías oficiales de Microsoft

---

## 9. Cambios y Actualizaciones

- **Versión actual**: 1.0
- **Última revisión**: 2025-02-16
- **Próxima revisión**: 2025-05-16 (3 meses)

**Regla**: Cualquier cambio a estas reglas requiere:
1. Aprobación de al menos 2 mantenedores
2. Actualización de versión
3. Notificación al equipo
4. Actualización de scripts existentes

---

## 10. Contacto y Soporte

Para preguntas sobre seguridad de modelos:
- **Issue**: Crear issue con label `security`
- **Urgente**: Contactar mantenedores directamente
- **Reportar vulnerabilidad**: Usar proceso de seguridad responsable

