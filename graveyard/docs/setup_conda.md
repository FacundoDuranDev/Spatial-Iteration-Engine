# Instalación de Conda y entorno del proyecto

## Conda ya instalado

Miniconda está en: **`~/miniconda3`**

Para que el comando `conda` esté disponible en tu terminal:

1. **Abre una terminal nueva** (o ejecuta `source ~/.bashrc`).
2. Comprueba: `conda --version` (debería mostrar algo como `conda 25.11.1`).

## Crear el entorno del proyecto

En una terminal (con `conda` en el PATH), desde la raíz del repo:

```bash
cd /home/fissure/repos/Spatial-Iteration-Engine
conda env create -f environment.yml
```

La primera vez tarda varios minutos (descarga Python, CMake, compiladores, numpy).

## Activar y usar

```bash
conda activate spatial-iteration-engine
pip install -r python/requirements.txt
./cpp/build.sh
```

Para que Python encuentre el paquete y los módulos C++:

```bash
export PYTHONPATH="$(pwd)/python:$(pwd)/cpp/build:$PYTHONPATH"
python -c "import ascii_stream_engine; import filters_cpp; print('OK')"
```

## Si algo falla

- **`conda: command not found`** → Abre una terminal nueva o ejecuta `source ~/.bashrc` (conda se añadió ahí).
- **El env ya existe** → `conda activate spatial-iteration-engine` y listo. Para recrear: `conda env remove -n spatial-iteration-engine` y luego `conda env create -f environment.yml` de nuevo.
