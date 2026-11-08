"""Resuelve el usuario MCP (BLOG_MCP_ACTOR o fallbacks de otros paquetes MCP)."""

from django.conf import settings
from django.utils.module_loading import import_string

from .errores import ServicioError


def usuario_mcp():
    path = (
        getattr(settings, 'BLOG_MCP_ACTOR', None)
        or getattr(settings, 'TESTS_PRECAVIDOS_MCP_ACTOR', None)
        or getattr(settings, 'SIMULADOR_MCP_ACTOR', None)
    )
    if not path:
        raise ServicioError(
            'Falta settings.BLOG_MCP_ACTOR '
            '(o TESTS_PRECAVIDOS_MCP_ACTOR / SIMULADOR_MCP_ACTOR).'
        )
    try:
        resolver = import_string(path)
    except ImportError as exc:
        raise ServicioError(f'No se pudo importar actor MCP={path!r}.') from exc
    return resolver()
