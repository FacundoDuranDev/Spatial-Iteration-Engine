# Makefile para Spatial Iteration Engine
# Comandos comunes de desarrollo

.PHONY: help install build test format lint clean setup pre-commit-install pre-commit-run cpp-build cpp-clean run-preview run-basic

# Variables
PYTHON := python3
PYTHONPATH := python:cpp/build
VENV := .venv
CONDA_ENV := spatial-iteration-engine

help: ## Mostrar esta ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Configurar entorno de desarrollo completo
	@echo "🚀 Configurando entorno de desarrollo..."
	@if command -v conda > /dev/null; then \
		echo "📦 Usando Conda..."; \
		conda env create -f environment.yml || conda env update -f environment.yml; \
		conda activate $(CONDA_ENV) && pip install -r python/requirements.txt && pip install -e python/[dev]; \
	else \
		echo "📦 Usando venv..."; \
		$(PYTHON) -m venv $(VENV); \
		. $(VENV)/bin/activate && pip install --upgrade pip && pip install -r requirements-build.txt && pip install -r python/requirements.txt && pip install -e python/[dev]; \
	fi
	@echo "✅ Entorno configurado. Activa con: conda activate $(CONDA_ENV) o source $(VENV)/bin/activate"

install: ## Instalar dependencias Python
	@echo "📦 Instalando dependencias..."
	$(PYTHON) -m pip install -r python/requirements.txt
	$(PYTHON) -m pip install -e python/[dev]

pre-commit-install: ## Instalar pre-commit hooks
	@echo "🔧 Instalando pre-commit hooks..."
	pre-commit install
	@echo "✅ Pre-commit hooks instalados"

pre-commit-run: ## Ejecutar pre-commit en todos los archivos
	@echo "🔍 Ejecutando pre-commit hooks..."
	pre-commit run --all-files

format: ## Formatear código Python (black + isort)
	@echo "🎨 Formateando código..."
	black python/ --line-length=100
	isort python/ --profile=black --line-length=100
	@echo "✅ Código formateado"

lint: ## Ejecutar linters (flake8)
	@echo "🔍 Ejecutando linters..."
	flake8 python/ --max-line-length=100 --extend-ignore=E203,W503
	@echo "✅ Linting completado"

test: ## Ejecutar tests
	@echo "🧪 Ejecutando tests..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest python/ascii_stream_engine/tests -v
	@echo "✅ Tests completados"

test-cov: ## Ejecutar tests con coverage
	@echo "🧪 Ejecutando tests con coverage..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest python/ascii_stream_engine/tests --cov=python/ascii_stream_engine --cov-report=html --cov-report=term
	@echo "✅ Coverage report en htmlcov/index.html"

cpp-build: ## Compilar módulos C++
	@echo "🔨 Compilando módulos C++..."
	cd cpp && ./build.sh
	@echo "✅ Módulos C++ compilados"

cpp-clean: ## Limpiar build de C++
	@echo "🧹 Limpiando build de C++..."
	rm -rf cpp/build/*
	@echo "✅ Build limpiado"

build: cpp-build ## Compilar todo (C++ y Python)
	@echo "✅ Build completo"

clean: cpp-clean ## Limpiar archivos generados
	@echo "🧹 Limpiando archivos generados..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	rm -rf .coverage
	@echo "✅ Limpieza completada"

run-preview: ## Ejecutar preview (MVP_02)
	@echo "🎬 Ejecutando preview..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) python/ascii_stream_engine/examples/stream_with_preview.py

run-basic: ## Ejecutar basic stream
	@echo "🎬 Ejecutando basic stream..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) python/ascii_stream_engine/examples/basic_stream.py

check: format lint test ## Ejecutar todas las verificaciones (format + lint + test)
	@echo "✅ Todas las verificaciones pasaron"

dev-setup: setup pre-commit-install ## Setup completo para desarrollo (setup + pre-commit)
	@echo "✅ Entorno de desarrollo listo!"

.DEFAULT_GOAL := help

