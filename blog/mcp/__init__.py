"""MCP del blog — servicios + registro de tools.

El host provee OAuth/ASGI y ``make_herramienta``; este módulo registra las tools.
"""

from .errores import ServicioError
from .tools import registrar

__all__ = ['ServicioError', 'registrar']
