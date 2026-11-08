"""Adapter opcional de metadata (país/nivel) por proyecto."""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string


class NoOpMetadataAdapter:
    """Default: sin filtrado ni asignación de país."""

    pais_obligatorio = False

    def filtrar_qs(self, qs, *, modelo: str, pais: str = ''):
        return qs

    def asignar(self, obj, *, modelo: str, pais: str = '', nivel: str = '') -> None:
        return None

    def enriquecer(self, payload: dict, obj, *, modelo: str) -> dict:
        return payload


def get_metadata_adapter():
    path = getattr(settings, 'BLOG_MCP_METADATA_ADAPTER', None)
    if not path:
        return NoOpMetadataAdapter()
    if isinstance(path, type):
        return path()
    cls_or_factory = import_string(path)
    if isinstance(cls_or_factory, type):
        return cls_or_factory()
    return cls_or_factory()
