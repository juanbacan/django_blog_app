"""Registro de tools MCP del blog."""

from mcp.types import ToolAnnotations

from . import servicios as servicio_blog

SOLO_LECTURA = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=False,
)
ESCRITURA = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
)
ESCRITURA_EXTERNA = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=True,
)
DESTRUCTIVA = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    openWorldHint=False,
)


def registrar(servidor, make_herramienta):
    """Registra todas las tools del blog en el servidor MCP del host."""
    _herramienta = make_herramienta(servidor)

    @_herramienta(
        'listar_categorias_blog',
        'Lista categorías del blog (árbol plano: id, nombre, slug, parent_slug, activo). '
        "Filtro activo: true, false o '' (todas). "
        'pais opcional (codigo_iso) si el host usa un adapter multi-país.',
        annotations=SOLO_LECTURA,
    )
    def listar_categorias_blog(activo: str = '', pais: str = '') -> dict:
        return servicio_blog.listar_categorias_blog(activo=activo, pais=pais)

    @_herramienta(
        'crear_categoria_blog',
        'Crea una categoría del blog. slug vacío → slugify(nombre). parent_slug opcional. '
        'pais opcional salvo que el adapter del host lo exija (pais_obligatorio).',
        annotations=ESCRITURA,
    )
    def crear_categoria_blog(
        nombre: str,
        slug: str = '',
        description: str = '',
        parent_slug: str = '',
        activo: bool = True,
        pais: str = '',
    ) -> dict:
        return servicio_blog.crear_categoria_blog(
            nombre=nombre,
            slug=slug,
            description=description,
            parent_slug=parent_slug,
            activo=activo,
            pais=pais,
        )

    @_herramienta(
        'actualizar_categoria_blog',
        'Actualiza una categoría del blog (id o slug). parent_slug vacío/"none" quita el padre. '
        'Para ocultar usa activo=false (no hay borrado en v1). '
        'pais opcional para reasignar metadata.',
        annotations=ESCRITURA,
    )
    def actualizar_categoria_blog(
        identificador: str,
        nombre: str = '',
        slug: str = '',
        description: str = '',
        parent_slug: str = '',
        activo: bool | None = None,
        pais: str = '',
    ) -> dict:
        return servicio_blog.actualizar_categoria_blog(
            identificador,
            nombre=nombre,
            slug=slug,
            description=description,
            parent_slug=parent_slug,
            activo=activo,
            pais=pais,
        )

    @_herramienta(
        'listar_posts',
        'Lista posts del blog. Por defecto solo activos. '
        "activo: true|false|'' (todos). Filtros: texto, categoria (slug). Pagina con offset. "
        'pais opcional si el host usa adapter multi-país.',
        annotations=SOLO_LECTURA,
    )
    def listar_posts(
        texto: str = '',
        categoria: str = '',
        activo: str = 'true',
        limite: int = 20,
        offset: int = 0,
        pais: str = '',
    ) -> dict:
        return servicio_blog.listar_posts(
            texto=texto,
            categoria=categoria,
            activo=activo,
            limite=limite,
            offset=offset,
            pais=pais,
        )

    @_herramienta(
        'obtener_post',
        'Detalle de un post (id o slug): meta, categorías, bloques de contenido e imagen URL si existe.',
        annotations=SOLO_LECTURA,
    )
    def obtener_post(identificador: str) -> dict:
        return servicio_blog.obtener_post(identificador)

    @_herramienta(
        'crear_post',
        'Crea un post con un bloque HTML inicial. categorias = lista de slugs existentes. '
        'slug vacío → slugify(titulo) con sufijo si choca. '
        'pais opcional salvo que el adapter del host lo exija.',
        annotations=ESCRITURA,
    )
    def crear_post(
        titulo: str,
        contenido: str,
        categorias: list[str] | None = None,
        slug: str = '',
        fecha: str = '',
        meta_title: str = '',
        meta_keywords: str = '',
        meta_description: str = '',
        activo: bool = True,
        pais: str = '',
    ) -> dict:
        return servicio_blog.crear_post(
            titulo=titulo,
            contenido=contenido,
            categorias=categorias or [],
            slug=slug,
            fecha=fecha,
            meta_title=meta_title,
            meta_keywords=meta_keywords,
            meta_description=meta_description,
            activo=activo,
            pais=pais,
        )

    @_herramienta(
        'actualizar_post',
        'Actualiza campos de un post (id o slug). Si pasas categorias, reemplaza el M2M completo. '
        'pais opcional para reasignar metadata.',
        annotations=ESCRITURA,
    )
    def actualizar_post(
        identificador: str,
        titulo: str = '',
        slug: str = '',
        fecha: str = '',
        meta_title: str = '',
        meta_keywords: str = '',
        meta_description: str = '',
        activo: bool | None = None,
        categorias: list[str] | None = None,
        pais: str = '',
    ) -> dict:
        return servicio_blog.actualizar_post(
            identificador,
            titulo=titulo,
            slug=slug,
            fecha=fecha,
            meta_title=meta_title,
            meta_keywords=meta_keywords,
            meta_description=meta_description,
            activo=activo,
            categorias=categorias,
            pais=pais,
        )

    @_herramienta(
        'activar_post',
        'Marca un post como activo (visible).',
        annotations=ESCRITURA,
    )
    def activar_post(identificador: str) -> dict:
        return servicio_blog.activar_post(identificador)

    @_herramienta(
        'desactivar_post',
        'Marca un post como inactivo (oculto en el sitio).',
        annotations=ESCRITURA,
    )
    def desactivar_post(identificador: str) -> dict:
        return servicio_blog.desactivar_post(identificador)

    @_herramienta(
        'eliminar_post',
        'Borra un post de forma permanente. Requiere confirmacion=true.',
        annotations=DESTRUCTIVA,
    )
    def eliminar_post(identificador: str, confirmacion: bool = False) -> dict:
        return servicio_blog.eliminar_post(identificador, confirmacion=confirmacion)

    @_herramienta(
        'agregar_contenido_post',
        'Añade un bloque HTML al post. orden=0 lo coloca al final.',
        annotations=ESCRITURA,
    )
    def agregar_contenido_post(
        identificador: str,
        contenido: str,
        orden: int = 0,
    ) -> dict:
        return servicio_blog.agregar_contenido_post(
            identificador, contenido, orden=orden
        )

    @_herramienta(
        'actualizar_contenido_post',
        'Actualiza el HTML y/o el orden de un bloque ContenidoBlog.',
        annotations=ESCRITURA,
    )
    def actualizar_contenido_post(
        contenido_id: int,
        contenido: str = '',
        orden: int | None = None,
    ) -> dict:
        return servicio_blog.actualizar_contenido_post(
            contenido_id, contenido=contenido, orden=orden
        )

    @_herramienta(
        'eliminar_contenido_post',
        'Elimina un bloque de contenido del post.',
        annotations=DESTRUCTIVA,
    )
    def eliminar_contenido_post(contenido_id: int) -> dict:
        return servicio_blog.eliminar_contenido_post(contenido_id)

    @_herramienta(
        'reordenar_contenidos_post',
        'Reordena los bloques de un post. Debe incluir todos los contenido_ids.',
        annotations=ESCRITURA,
    )
    def reordenar_contenidos_post(
        identificador: str, contenido_ids: list[int]
    ) -> dict:
        return servicio_blog.reordenar_contenidos_post(identificador, contenido_ids)

    @_herramienta(
        'obtener_url_subida_imagen_blog',
        'URL firmada (PUT) para subir una imagen a R2/CDN. '
        'Después llama asignar_imagen_post con imagen_r2_key=key. '
        'content_type típico: image/webp, image/jpeg, image/png.',
        annotations=ESCRITURA,
    )
    def obtener_url_subida_imagen_blog(
        filename: str = 'imagen.webp',
        content_type: str = 'image/webp',
    ) -> dict:
        return servicio_blog.obtener_url_subida_imagen_blog(
            filename=filename,
            content_type=content_type,
        )

    @_herramienta(
        'asignar_imagen_post',
        'Asigna la imagen principal de un post (id o slug). '
        'Pasa exactamente una fuente no vacía: imagen_r2_key (preferido), imagen_url o imagen_base64. '
        'Omite el resto de fuentes (no envíes null). '
        'optimizar=true (default) genera WebP 1200×630 y guarda en blog/ (CDN R2 si está activo); alt opcional.',
        annotations=ESCRITURA,
    )
    def asignar_imagen_post(
        identificador: str,
        imagen_url: str = '',
        imagen_base64: str = '',
        imagen_r2_key: str = '',
        imagen_filename: str = '',
        imagen_content_type: str = '',
        alt: str = '',
        reemplazar_principal: bool = True,
        optimizar: bool = True,
        ancho: int = 1200,
        alto: int = 630,
    ) -> dict:
        return servicio_blog.asignar_imagen_post(
            identificador,
            imagen_url=imagen_url,
            imagen_base64=imagen_base64,
            imagen_r2_key=imagen_r2_key,
            imagen_filename=imagen_filename,
            imagen_content_type=imagen_content_type,
            alt=alt,
            reemplazar_principal=reemplazar_principal,
            optimizar=optimizar,
            ancho=ancho,
            alto=alto,
        )

    @_herramienta(
        'publicar_post_facebook',
        'Publica un post del blog en la Page de Facebook. '
        "modo='draft' (default) crea borrador en Business Suite; modo='public' publica en vivo. "
        'titulo/descripcion/primer_comentario opcionales (vacío = defaults del post). '
        'dry_run=true solo arma el payload sin llamar a Graph. '
        'forzar=true crea un post nuevo aunque ya exista uno asociado.',
        annotations=ESCRITURA_EXTERNA,
    )
    def publicar_post_facebook(
        identificador: str,
        titulo: str = '',
        descripcion: str = '',
        primer_comentario: str = '',
        modo: str = 'draft',
        dry_run: bool = False,
        forzar: bool = False,
        incluir_link: bool = True,
    ) -> dict:
        return servicio_blog.publicar_post_facebook(
            identificador,
            titulo=titulo,
            descripcion=descripcion,
            primer_comentario=primer_comentario,
            modo=modo,
            dry_run=dry_run,
            forzar=forzar,
            incluir_link=incluir_link,
        )

    @_herramienta(
        'hacer_publico_post_facebook',
        'Pasa a público un draft de Facebook ya creado y publica el primer comentario. '
        'primer_comentario vacío usa el guardado / link al artículo.',
        annotations=ESCRITURA_EXTERNA,
    )
    def hacer_publico_post_facebook(
        identificador: str,
        primer_comentario: str = '',
    ) -> dict:
        return servicio_blog.hacer_publico_post_facebook(
            identificador,
            primer_comentario=primer_comentario,
        )

    @_herramienta(
        'estado_facebook_post',
        'Devuelve el estado local de publicación en Facebook de un post (id o slug). '
        'No llama a Graph API.',
        annotations=SOLO_LECTURA,
    )
    def estado_facebook_post(identificador: str) -> dict:
        return servicio_blog.estado_facebook_post(identificador)
