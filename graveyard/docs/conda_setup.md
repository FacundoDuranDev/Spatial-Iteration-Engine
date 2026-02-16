# Entorno Conda – Spatial-Iteration-Engine

Guía paso a paso para crear, activar y usar el entorno Conda del proyecto. Este entorno incluye **Python**, **CMake** y un **compilador C++**, para poder desarrollar y compilar tanto el código Python como los módulos C++ (filtros, bridge pybind11) sin instalar herramientas a nivel de sistema.

---

## 1. Instalación de Conda

Si aún no tienes Conda, instala **Miniconda** (recomendado, ligero) o **Anaconda** (incluye más paquetes y una interfaz gráfica).

### Opción A: Miniconda (recomendado)

1. **Descargar el instalador** según tu sistema:
   - [Miniconda – Linux](https://docs.conda.io/en/latest/miniconda.html#linux-installers)
   - [Miniconda – macOS](https://docs.conda.io/en/latest/miniconda.html#macos-installers)
   - [Miniconda – Windows](https://docs.conda.io/en/latest/miniconda.html#windows-installers)

2. **Linux (ejemplo x86_64):**
   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   bash Miniconda3-latest-Linux-x86_64.sh
   ```
   Sigue las preguntas (acepta la licencia, confirma la ruta de instalación). Al final, el instalador puede preguntar si quieres ejecutar `conda init`: responde **yes** para que `conda` esté disponible en todas las terminales.

3. **macOS:**  
   Descarga el instalador `.pkg` o el script `.sh` desde la página de Miniconda y ejecútalo. Si usas el script, es similar a Linux; si usas el `.pkg`, sigue el asistente. Luego abre una nueva terminal.

4. **Windows:**  
   Descarga el instalador `.exe`, ejecútalo y sigue el asistente. Marca la opción para añadir Conda al PATH si te la ofrece. Al terminar, abre **Anaconda Prompt** o una terminal nueva (CMD o PowerShell).

5. **Inicializar Conda en la terminal (si `conda` no se reconoce):**
   ```bash
   # En Linux/macOS con bash:
   conda init bash
   # Luego cierra y abre de nuevo la terminal.

   # En Linux con zsh:
   conda init zsh

   # En Windows (PowerShell), a veces hace falta ejecutar:
   # & 'C:\Users\TU_USUARIO\miniconda3\Scripts\conda.exe' init powershell
   ```

6. **Comprobar que Conda está instalado:**
   ```bash
   conda --version
   ```
   Deberías ver algo como `conda 24.x.x`. Si no, reinicia la terminal o revisa que la ruta de instalación esté en tu PATH.

### Opción B: Anaconda

- Descarga desde [https://www.anaconda.com/download](https://www.anaconda.com/download), elige tu sistema operativo e instala. El proceso es similar: ejecutar el instalador, aceptar licencia y, si se ofrece, inicializar Conda para tu shell. Luego verifica con `conda --version`.

---

## 2. Activar Conda en cada sesión

Conda se “activa” a nivel de shell: hasta que no hagas `conda activate`, el comando `conda` puede no estar disponible en terminales nuevas (sobre todo si no ejecutaste `conda init`).

- **Si ya hiciste `conda init`:** cada vez que abres una terminal, Conda ya está “cargado” y puedes usar `conda activate ...` directamente.
- **Si no:** en Linux/macOS puedes cargar Conda a mano en cada terminal:
  ```bash
  source ~/miniconda3/bin/activate   # o la ruta donde instalaste (ej. ~/anaconda3)
  ```
  En Windows, usa **Anaconda Prompt** o ejecuta antes el script de activación que instala Conda.

Para trabajar en este proyecto no hace falta activar el entorno base de Conda; solo necesitas poder ejecutar `conda`. El siguiente paso es crear y activar el entorno **spatial-iteration-engine**.

---

## 3. Crear el entorno del proyecto

Desde la **raíz del repositorio** (`Spatial-Iteration-Engine/`):

```bash
conda env create -f environment.yml
```

Esto crea un entorno llamado `spatial-iteration-engine` con:

- Python ≥ 3.8  
- pip  
- CMake ≥ 3.15  
- Compiladores (gcc/g++ en Linux, clang en macOS)  
- NumPy  

Puede tardar unos minutos la primera vez.

---

## 4. Activar el entorno del proyecto

Cada vez que abras una terminal para trabajar en el proyecto, activa el entorno:

```bash
conda activate spatial-iteration-engine
```

El prompt debería mostrar algo como `(spatial-iteration-engine)` al inicio. A partir de ahí, `python`, `pip`, `cmake` y el compilador C++ son los del entorno.

Para desactivar y volver a tu entorno por defecto:

```bash
conda deactivate
```

---

## 5. Instalar dependencias Python del proyecto

Con el entorno activado, instala las dependencias del motor Python:

```bash
pip install -r python/requirements.txt
```

Opcional: si quieres instalar el paquete en modo editable para desarrollo:

```bash
pip install -e python/
```

(Asumiendo que en `python/` hay un `setup.py` o `pyproject.toml`; si no, el paso anterior basta.)

---

## 6. Compilar los módulos C++

Para compilar filtros C++ y el bridge pybind11:

```bash
conda activate spatial-iteration-engine
./cpp/build.sh
```

El script usa CMake y el compilador del entorno; los `.so` (o equivalentes) quedarán en `cpp/build/`.  
Para que Python pueda importar el módulo, suele hacerse desde la raíz del repo o añadiendo `cpp/build` al `PYTHONPATH` según cómo esté configurado el proyecto.

---

## 7. Resumen rápido: “cada día que trabajo en el proyecto”

1. Abrir terminal en la raíz del repo.  
2. `conda activate spatial-iteration-engine`  
3. Si cambiaste código C++: `./cpp/build.sh`  
4. Ejecutar el motor o tests como siempre (por ejemplo `python -m ascii_stream_engine` o los scripts que uses).

---

## 8. Comandos útiles

| Acción | Comando |
|--------|--------|
| Listar entornos | `conda env list` |
| Activar | `conda activate spatial-iteration-engine` |
| Desactivar | `conda deactivate` |
| Eliminar el entorno | `conda env remove -n spatial-iteration-engine` |
| Recrear desde cero | `conda env remove -n spatial-iteration-engine` y luego `conda env create -f environment.yml` |
| Ver paquetes instalados | `conda list` |

---

## 9. Problemas frecuentes

- **`conda: command not found`**  
  Conda no está en el PATH. Revisa la instalación y, en Linux/macOS, ejecuta el script de inicialización que te indica el instalador (por ejemplo `conda init bash`).

- **El build de C++ falla por “cmake not found” o “no compiler”**  
  Asegúrate de tener el entorno activado (`conda activate spatial-iteration-engine`) antes de ejecutar `./cpp/build.sh`.

- **Cambios en `environment.yml`**  
  Para aplicarlos puedes actualizar el entorno con  
  `conda env update -f environment.yml -n spatial-iteration-engine`  
  o eliminar el entorno y volver a crearlo con `conda env create -f environment.yml`.

Con esto ya puedes levantar y usar el entorno Conda del proyecto de forma repetible.
