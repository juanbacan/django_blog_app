# MCP del blog (`blog.mcp`)

Tools MCP para categorías, posts, bloques de contenido e imágenes (R2/CDN).

```python
from blog.mcp import registrar as registrar_blog
from mi_app_mcp.runtime import make_herramienta

registrar_blog(servidor, make_herramienta)
```

## Settings

```python
BLOG_MCP_ACTOR = 'mi_app.servicios.actor.usuario_mcp'
# Opcional: cae a TESTS_PRECAVIDOS_MCP_ACTOR o SIMULADOR_MCP_ACTOR si no se define.

# Proyectos multi-país (ej. evaluación-docente):
BLOG_MCP_METADATA_ADAPTER = 'applications.main.mcp_metadata.BlogMetadataAdapter'

# Proyectos single-country: omitir el adapter (no-op, pais_obligatorio=False).
API_IMPORT_MAX_PREGUNTAS = 100  # opcional, tope de paginación listar_posts
```

### Contrato del adapter

```python
class MiAdapter:
    pais_obligatorio = True  # opcional; default False en NoOp

    def filtrar_qs(self, qs, *, modelo: str, pais: str = ''): ...
    def asignar(self, obj, *, modelo: str, pais: str = '', nivel: str = ''): ...
    def enriquecer(self, payload: dict, obj, *, modelo: str) -> dict: ...
```

`modelo` ∈ `categoria` | `post`.

## Checklist de integración

- [ ] Host MCP (OAuth/ASGI) listo
- [ ] Paquete `mcp` instalado en el host (no va en install_requires del blog)
- [ ] `BLOG_MCP_ACTOR` (o actor compartido de tests/simulador)
- [ ] Adapter de país solo si el proyecto tiene Metadata*
- [ ] `registrar_blog(servidor, make_herramienta)` en el `server.py` del host
- [ ] Smoke: `listar_categorias_blog`, `listar_posts`, `obtener_post`

## Versión

Incluido desde **django-blog-app 0.1.34+**.

Tras cambios en `blog.mcp`, sube la versión en `setup.py` del paquete antes de publicar.
