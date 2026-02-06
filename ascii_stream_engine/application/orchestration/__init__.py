"""Orquestación del pipeline de procesamiento de frames."""

from .pipeline_orchestrator import PipelineOrchestrator
from .stage_executor import StageExecutor, StageResult

__all__ = ["PipelineOrchestrator", "StageExecutor", "StageResult"]

