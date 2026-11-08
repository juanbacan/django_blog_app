"""Gestión del blog (posts, categorías, bloques de contenido) vía MCP."""

import re
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify

from blog.models import Categoria, ContenidoBlog, ImagenPost, Post

from .actor import usuario_mcp
from .errores import ServicioError
from . import imagenes as r2_imagenes
from .metadata import get_metadata_adapter

# Formato Open Graph / redes: horizontal, carga rápida en celular.
_IMAGEN_ANCHO_DEFAULT = 1200
_IMAGEN_ALTO_DEFAULT = 630
_IMAGEN_WEBP_QUALITY = 75


def _limite(valor, defecto=20) -> int:
    tope = int(getattr(settings, 'API_IMPORT_MAX_PREGUNTAS', 100) or 100)
    try:
        numero = int(valor if valor not in (None, '') else defecto)
    except (TypeError, ValueError):
        numero = defecto
    return max(1, min(numero, tope))


def _texto_plano(html, limite_chars=180) -> str:
    texto = re.sub(r'<[^>]+>', ' ', html or '')
    texto = re.sub(r'\s+', ' ', texto).strip()
    if len(texto) <= limite_chars:
        return texto
    return texto[:limite_chars].rstrip() + '…'


def _titulo(valor: str) -> str:
    titulo = (valor or '').strip()
    if not titulo:
        raise ServicioError('El título es obligatorio.')
    if len(titulo) > 500:
        raise ServicioError('El título no puede superar 500 caracteres.')
    return titulo


def _slug_valor(valor: str, etiqueta: str = 'slug') -> str:
    slug = (valor or '').strip()
    if not slug:
        raise ServicioError(f'El {etiqueta} es obligatorio.')
    if len(slug) > 100:
        raise ServicioError(f'El {etiqueta} no puede superar 100 caracteres.')
    return slug


def _slug_unico_post(base: str, excluir_id=None) -> str:
    base = slugify(base or '')[:100] or 'post'
    slug = base
    n = 2
    while True:
        qs = Post.objects.filter(slug=slug)
        if excluir_id is not None:
            qs = qs.exclude(pk=excluir_id)
        if not qs.exists():
            return slug
        sufijo = f'-{n}'
        slug = base[: max(1, 100 - len(sufijo))] + sufijo
        n += 1


def _slug_unico_categoria(base: str, excluir_id=None) -> str:
    base = slugify(base or '')[:100] or 'categoria'
    slug = base
    n = 2
    while True:
        qs = Categoria.objects.filter(slug=slug)
        if excluir_id is not None:
            qs = qs.exclude(pk=excluir_id)
        if not qs.exists():
            return slug
        sufijo = f'-{n}'
        slug = base[: max(1, 100 - len(sufijo))] + sufijo
        n += 1


def _parse_fecha_post(valor: str):
    valor = (valor or '').strip()
    if not valor:
        return None
    dt = parse_datetime(valor)
    if dt is None:
        fecha = parse_date(valor)
        if fecha is None:
            raise ServicioError('La fecha debe ser YYYY-MM-DD o datetime ISO.')
        dt = datetime.combine(fecha, datetime.min.time())
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_activo_filtro(valor, *, defecto: bool | None = True) -> bool | None:
    """True=solo activos, False=solo inactivos, None=todos."""
    if valor is True:
        return True
    if valor is False:
        return False
    if valor is None:
        return defecto
    texto = str(valor).strip().casefold()
    if texto in ('', 'todos', 'all', 'none'):
        return None
    if texto in ('1', 'true', 'si', 'sí', 'activo', 'activos'):
        return True
    if texto in ('0', 'false', 'no', 'inactivo', 'inactivos'):
        return False
    raise ServicioError("activo inválido. Usa true, false o '' (todos).")


def _obtener_post(identificador: str) -> Post:
    texto = str(identificador if identificador is not None else '').strip()
    if not texto:
        raise ServicioError('Falta el identificador del post (id o slug).')
    if texto.isdigit():
        post = Post.objects.filter(pk=int(texto)).first()
    else:
        post = Post.objects.filter(slug__iexact=texto).first()
    if post is None:
        raise ServicioError(f'No existe el post «{texto}».')
    return post


def _obtener_categoria(identificador: str) -> Categoria:
    texto = str(identificador if identificador is not None else '').strip()
    if not texto:
        raise ServicioError('Falta el identificador de la categoría (id o slug).')
    if texto.isdigit():
        cat = Categoria.objects.filter(pk=int(texto)).first()
    else:
        cat = Categoria.objects.filter(slug__iexact=texto).first()
    if cat is None:
        raise ServicioError(f'No existe la categoría «{texto}».')
    return cat


def _obtener_contenido(contenido_id) -> ContenidoBlog:
    try:
        contenido_id = int(contenido_id)
    except (TypeError, ValueError):
        raise ServicioError('contenido_id inválido.') from None
    bloque = ContenidoBlog.objects.select_related('post').filter(pk=contenido_id).first()
    if bloque is None:
        raise ServicioError('El bloque de contenido no existe.')
    return bloque


def _resolver_categorias(slugs) -> list[Categoria]:
    if not slugs:
        return []
    if isinstance(slugs, str):
        slugs = [s.strip() for s in slugs.split(',') if s.strip()]
    if not isinstance(slugs, (list, tuple)):
        raise ServicioError('categorias debe ser una lista de slugs.')
    resultado = []
    vistos = set()
    for item in slugs:
        slug = str(item or '').strip()
        if not slug or slug in vistos:
            continue
        cat = Categoria.objects.filter(slug__iexact=slug).first()
        if cat is None:
            raise ServicioError(f'No existe la categoría «{slug}».')
        resultado.append(cat)
        vistos.add(slug.casefold())
    return resultado


def _resumen_categoria(cat: Categoria, adapter=None) -> dict:
    adapter = adapter or get_metadata_adapter()
    data = {
        'id': cat.id,
        'nombre': cat.nombre,
        'slug': cat.slug,
        'parent_slug': cat.parent.slug if cat.parent_id else '',
        'activo': bool(cat.activo),
        'description': cat.description or '',
    }
    return adapter.enriquecer(data, cat, modelo='categoria')


def _resumen_post(post: Post, adapter=None) -> dict:
    adapter = adapter or get_metadata_adapter()
    data = {
        'id': post.id,
        'titulo': post.titulo,
        'slug': post.slug,
        'fecha': post.fecha.isoformat() if post.fecha else '',
        'activo': bool(post.activo),
        'meta_title': post.meta_title or '',
        'meta_description': _texto_plano(post.meta_description or '', limite_chars=180),
        'url': post.mi_url_relativa(),
        'categorias': list(post.categorias.values_list('slug', flat=True)),
    }
    return adapter.enriquecer(data, post, modelo='post')


def _detalle_post(post: Post) -> dict:
    contenidos = [
        {
            'id': bloque.id,
            'orden': bloque.orden,
            'contenido': bloque.contenido or '',
            'contenido_plano': _texto_plano(bloque.contenido or ''),
        }
        for bloque in post.mis_descripciones()
    ]
    payload = {
        'ok': True,
        'id': post.id,
        'titulo': post.titulo,
        'slug': post.slug,
        'fecha': post.fecha.isoformat() if post.fecha else '',
        'activo': bool(post.activo),
        'meta_title': post.meta_title or '',
        'meta_keywords': post.meta_keywords or '',
        'meta_description': post.meta_description or '',
        'url': post.mi_url_relativa(),
        'url_absoluta': post.mi_url_absoluta,
        'categorias': [
            {'id': c.id, 'nombre': c.nombre, 'slug': c.slug}
            for c in post.categorias.all().order_by('nombre')
        ],
        'contenidos': contenidos,
        'imagen': post.mi_imagen() or '',
        'imagen_alt': (
            post.mi_imagen_alt() if hasattr(post, 'mi_imagen_alt') else (post.titulo or '')
        ),
        'facebook': {
            'estado': getattr(post, 'facebook_estado', 'no_publicado'),
            'publicado': bool(getattr(post, 'publicado_facebook', False)),
            'post_id': getattr(post, 'facebook_post_id', None) or '',
            'url': getattr(post, 'url_post_facebook', None) or '',
        },
    }
    return get_metadata_adapter().enriquecer(payload, post, modelo='post')


def _payload_imagen(
    imagen_url: str = '',
    imagen_base64: str = '',
    imagen_r2_key: str = '',
    imagen_filename: str = '',
    imagen_content_type: str = '',
) -> dict:
    url = (imagen_url or '').strip()
    b64 = (imagen_base64 or '').strip()
    r2_raw = (imagen_r2_key or '').strip()

    r2_key = ''
    if r2_raw:
        try:
            r2_key = r2_imagenes.normalize_r2_key(r2_raw)
        except ValueError as exc:
            raise ServicioError(str(exc)) from exc

    if url and not r2_key:
        own = r2_imagenes.extract_r2_key_from_url(url)
        if own:
            r2_key = own
            url = ''

    fuentes = [bool(url), bool(b64), bool(r2_key)]
    if sum(fuentes) != 1:
        raise ServicioError(
            'Indica exactamente una fuente: imagen_url, imagen_base64 o imagen_r2_key.'
        )
    if r2_key:
        return {'source': 'r2_key', 'r2_key': r2_key}
    if b64:
        return {
            'source': 'base64',
            'base64': b64,
            'filename': (imagen_filename or '').strip() or None,
            'content_type': (imagen_content_type or '').strip() or None,
        }
    return {'source': 'url', 'url': url}


def _optimizar_imagen_webp(
    content: bytes,
    *,
    ancho: int = _IMAGEN_ANCHO_DEFAULT,
    alto: int = _IMAGEN_ALTO_DEFAULT,
    quality: int = _IMAGEN_WEBP_QUALITY,
) -> tuple[str, bytes, dict]:
    """Recorta/escala a cover y exporta WebP (listo para CDN)."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ServicioError('Pillow no está instalado; no se puede optimizar la imagen.') from exc

    if not content:
        raise ServicioError('La imagen está vacía.')
    if ancho < 1 or alto < 1:
        raise ServicioError('ancho y alto deben ser positivos.')
    if quality < 1 or quality > 100:
        raise ServicioError('quality debe estar entre 1 y 100.')

    try:
        img = Image.open(BytesIO(content))
        img.load()
    except Exception as exc:
        raise ServicioError(f'No se pudo leer la imagen: {exc}') from exc

    img = img.convert('RGB')
    src_w, src_h = img.size
    target_ratio = ancho / alto
    src_ratio = src_w / src_h if src_h else target_ratio
    if src_ratio > target_ratio:
        new_w = int(round(src_h * target_ratio))
        left = max(0, (src_w - new_w) // 2)
        img = img.crop((left, 0, left + new_w, src_h))
    elif src_ratio < target_ratio:
        new_h = int(round(src_w / target_ratio))
        top = max(0, (src_h - new_h) // 2)
        img = img.crop((0, top, src_w, top + new_h))

    img = img.resize((ancho, alto), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format='WEBP', quality=quality, method=6)
    data = out.getvalue()
    return (
        'imagen.webp',
        data,
        {
            'width': ancho,
            'height': alto,
            'format': 'WEBP',
            'quality': quality,
            'bytes': len(data),
            'origen_width': src_w,
            'origen_height': src_h,
        },
    )


def _url_imagen_registro(imagen: ImagenPost) -> str:
    try:
        url = imagen.imagen.url if imagen.imagen else ''
    except Exception:
        return ''
    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/') or getattr(
        settings, 'URL_BASE', ''
    ).rstrip('/')
    return f'{site_url}{url}' if site_url else url


def _exigir_pais_si_adapter(adapter, pais: str) -> None:
    if getattr(adapter, 'pais_obligatorio', False) and not (pais or '').strip():
        raise ServicioError(
            'pais es obligatorio cuando el adapter de metadata del host lo requiere '
            '(codigo_iso, ej. ec, pe, cl).'
        )


def obtener_url_subida_imagen_blog(
    filename: str = 'imagen.webp',
    content_type: str = 'image/webp',
) -> dict:
    """URL firmada PUT → R2. Luego usa asignar_imagen_post con imagen_r2_key."""
    usuario_mcp()
    try:
        upload = r2_imagenes.generate_presigned_upload(
            filename=filename or 'imagen.webp',
            content_type=content_type or 'image/webp',
        )
    except ValueError as exc:
        raise ServicioError(str(exc)) from exc
    return {
        'ok': True,
        **upload,
        'instrucciones': (
            'Sube el archivo con PUT a upload_url (header Content-Type = content_type) '
            'y luego llama asignar_imagen_post con imagen_r2_key=key.'
        ),
    }


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
    ancho: int = _IMAGEN_ANCHO_DEFAULT,
    alto: int = _IMAGEN_ALTO_DEFAULT,
) -> dict:
    """
    Resuelve la imagen, la optimiza a WebP (1200×630 por defecto),
    la guarda en blog/ (R2/CDN si está activo) y la marca como principal.
    """
    usuario = usuario_mcp()
    post = _obtener_post(identificador)
    payload = _payload_imagen(
        imagen_url=imagen_url,
        imagen_base64=imagen_base64,
        imagen_r2_key=imagen_r2_key,
        imagen_filename=imagen_filename,
        imagen_content_type=imagen_content_type,
    )
    try:
        filename, content = r2_imagenes.resolve_image_bytes(payload)
    except ValueError as exc:
        raise ServicioError(str(exc)) from exc
    except Exception as exc:
        raise ServicioError(f'No se pudo obtener la imagen: {exc}') from exc

    meta_opt = None
    if optimizar:
        filename, content, meta_opt = _optimizar_imagen_webp(
            content, ancho=int(ancho), alto=int(alto)
        )
    elif not (filename or '').lower().endswith(('.webp', '.jpg', '.jpeg', '.png', '.gif')):
        filename = f'{(filename or "imagen").rsplit(".", 1)[0]}.webp'

    alt_texto = (alt or '').strip()
    if len(alt_texto) > 255:
        raise ServicioError('alt no puede superar 255 caracteres.')
    if not alt_texto:
        alt_texto = (post.titulo or '')[:255]

    tiene_alt = any(f.name == 'alt' for f in ImagenPost._meta.get_fields())

    try:
        with transaction.atomic():
            if reemplazar_principal:
                ImagenPost.objects.filter(post=post, principal=True).update(principal=False)

            datos = {
                'post': post,
                'principal': True,
                'created_by': usuario,
                'modified_by': usuario,
            }
            if tiene_alt:
                datos['alt'] = alt_texto
            imagen = ImagenPost(**datos)
            imagen.imagen.save(filename, ContentFile(content), save=True)
    except ServicioError:
        raise
    except Exception as exc:
        raise ServicioError(f'No se pudo guardar la imagen en el post: {exc}') from exc

    imagen_alt = getattr(imagen, 'alt', '') or '' if tiene_alt else alt_texto
    return {
        'ok': True,
        'post_id': post.id,
        'post_slug': post.slug,
        'imagen_id': imagen.id,
        'imagen_url': _url_imagen_registro(imagen) or post.mi_imagen() or '',
        'imagen_alt': imagen_alt,
        'principal': True,
        'cdn': bool(r2_imagenes.r2_configured()),
        'optimizacion': meta_opt,
        'alt_persistido': bool(tiene_alt),
    }


def listar_categorias_blog(activo: str = '', pais: str = '') -> dict:
    adapter = get_metadata_adapter()
    qs = Categoria.objects.select_related('parent').order_by('tree_id', 'lft')
    qs = adapter.filtrar_qs(qs, modelo='categoria', pais=pais)
    filtro = _parse_activo_filtro(activo, defecto=None)
    if filtro is not None:
        qs = qs.filter(activo=filtro)
    return {
        'ok': True,
        'categorias': [_resumen_categoria(c, adapter) for c in qs],
    }


def crear_categoria_blog(
    nombre: str,
    slug: str = '',
    description: str = '',
    parent_slug: str = '',
    activo: bool = True,
    pais: str = '',
) -> dict:
    usuario_mcp()
    adapter = get_metadata_adapter()
    _exigir_pais_si_adapter(adapter, pais)
    nombre = (nombre or '').strip()
    if not nombre:
        raise ServicioError('El nombre de la categoría es obligatorio.')
    if len(nombre) > 50:
        raise ServicioError('El nombre de la categoría no puede superar 50 caracteres.')
    if Categoria.objects.filter(nombre__iexact=nombre).exists():
        raise ServicioError(f'Ya existe una categoría con nombre «{nombre}».')
    slug_final = _slug_valor(slug) if slug else _slug_unico_categoria(nombre)
    if Categoria.objects.filter(slug__iexact=slug_final).exists():
        if slug:
            raise ServicioError(f'Ya existe una categoría con slug «{slug_final}».')
        slug_final = _slug_unico_categoria(slug_final)
    parent = None
    if parent_slug:
        parent = _obtener_categoria(parent_slug)
    description = (description or '').strip()
    cat = Categoria(
        nombre=nombre,
        slug=slug_final,
        description=description,
        parent=parent,
        activo=bool(activo),
    )
    cat.save()
    adapter.asignar(cat, modelo='categoria', pais=pais)
    return {'ok': True, **_resumen_categoria(cat, adapter)}


def actualizar_categoria_blog(
    identificador: str,
    nombre: str = '',
    slug: str = '',
    description: str = '',
    parent_slug: str = '',
    activo: bool | None = None,
    pais: str = '',
) -> dict:
    usuario_mcp()
    adapter = get_metadata_adapter()
    cat = _obtener_categoria(identificador)
    if nombre:
        nombre = nombre.strip()
        if len(nombre) > 50:
            raise ServicioError('El nombre de la categoría no puede superar 50 caracteres.')
        if (
            Categoria.objects.filter(nombre__iexact=nombre)
            .exclude(pk=cat.pk)
            .exists()
        ):
            raise ServicioError(f'Ya existe una categoría con nombre «{nombre}».')
        cat.nombre = nombre
    if slug:
        slug_final = _slug_valor(slug)
        if (
            Categoria.objects.filter(slug__iexact=slug_final)
            .exclude(pk=cat.pk)
            .exists()
        ):
            raise ServicioError(f'Ya existe una categoría con slug «{slug_final}».')
        cat.slug = slug_final
    if description != '':
        cat.description = description
    if parent_slug != '':
        if parent_slug in (None, '0', 'null', 'none'):
            cat.parent = None
        else:
            parent = _obtener_categoria(parent_slug)
            if parent.pk == cat.pk:
                raise ServicioError('Una categoría no puede ser padre de sí misma.')
            cat.parent = parent
    if activo is not None:
        cat.activo = bool(activo)
    cat.save()
    if pais:
        adapter.asignar(cat, modelo='categoria', pais=pais)
    return {'ok': True, **_resumen_categoria(cat, adapter)}


def listar_posts(
    texto: str = '',
    categoria: str = '',
    activo: str = 'true',
    limite: int = 20,
    offset: int = 0,
    pais: str = '',
) -> dict:
    adapter = get_metadata_adapter()
    qs = Post.objects.prefetch_related('categorias').order_by('-fecha', '-id')
    qs = adapter.filtrar_qs(qs, modelo='post', pais=pais)
    filtro_activo = _parse_activo_filtro(activo, defecto=True)
    if filtro_activo is not None:
        qs = qs.filter(activo=filtro_activo)
    texto = (texto or '').strip()
    if texto:
        qs = qs.filter(
            Q(titulo__icontains=texto)
            | Q(slug__icontains=texto)
            | Q(meta_description__icontains=texto)
            | Q(contenidoblog__contenido__icontains=texto)
        ).distinct()
    categoria = (categoria or '').strip()
    if categoria:
        qs = qs.filter(categorias__slug__iexact=categoria).distinct()
    tope = _limite(limite)
    try:
        inicio = max(0, int(offset or 0))
    except (TypeError, ValueError):
        inicio = 0
    total = qs.count()
    posts = [_resumen_post(p, adapter) for p in qs[inicio : inicio + tope]]
    return {
        'ok': True,
        'total': total,
        'offset': inicio,
        'limite': tope,
        'posts': posts,
    }


def obtener_post(identificador: str) -> dict:
    return _detalle_post(_obtener_post(identificador))


def crear_post(
    titulo: str,
    contenido: str,
    categorias=None,
    slug: str = '',
    fecha: str = '',
    meta_title: str = '',
    meta_keywords: str = '',
    meta_description: str = '',
    activo: bool = True,
    pais: str = '',
) -> dict:
    usuario = usuario_mcp()
    adapter = get_metadata_adapter()
    _exigir_pais_si_adapter(adapter, pais)
    titulo = _titulo(titulo)
    contenido = contenido if contenido is not None else ''
    if not str(contenido).strip():
        raise ServicioError('El contenido del post es obligatorio.')
    cats = _resolver_categorias(categorias or [])
    slug_final = _slug_valor(slug) if slug else _slug_unico_post(titulo)
    if Post.objects.filter(slug__iexact=slug_final).exists():
        if slug:
            slug_final = _slug_unico_post(slug_final)
        else:
            slug_final = _slug_unico_post(titulo)
    meta_title = (meta_title or '').strip()
    meta_keywords = (meta_keywords or '').strip()
    meta_description = (meta_description or '').strip()
    if len(meta_title) > 200:
        raise ServicioError('meta_title no puede superar 200 caracteres.')
    if len(meta_keywords) > 300:
        raise ServicioError('meta_keywords no puede superar 300 caracteres.')
    if len(meta_description) > 500:
        raise ServicioError('meta_description no puede superar 500 caracteres.')
    fecha_dt = _parse_fecha_post(fecha) or timezone.now()
    with transaction.atomic():
        post = Post(
            titulo=titulo,
            slug=slug_final,
            fecha=fecha_dt,
            activo=bool(activo),
            meta_title=meta_title or None,
            meta_keywords=meta_keywords or None,
            meta_description=meta_description or None,
            created_by=usuario,
        )
        post.save()
        adapter.asignar(post, modelo='post', pais=pais)
        if cats:
            post.categorias.set(cats)
        ContenidoBlog.objects.create(
            post=post,
            contenido=contenido,
            orden=1,
            created_by=usuario,
        )
    return _detalle_post(post)


def actualizar_post(
    identificador: str,
    titulo: str = '',
    slug: str = '',
    fecha: str = '',
    meta_title: str = '',
    meta_keywords: str = '',
    meta_description: str = '',
    activo: bool | None = None,
    categorias=None,
    pais: str = '',
) -> dict:
    usuario = usuario_mcp()
    adapter = get_metadata_adapter()
    post = _obtener_post(identificador)
    if titulo:
        post.titulo = _titulo(titulo)
    if slug:
        slug_final = _slug_valor(slug)
        if (
            Post.objects.filter(slug__iexact=slug_final)
            .exclude(pk=post.pk)
            .exists()
        ):
            raise ServicioError(f'Ya existe un post con slug «{slug_final}».')
        post.slug = slug_final
    if fecha:
        post.fecha = _parse_fecha_post(fecha)
    if meta_title != '':
        meta_title = meta_title.strip()
        if len(meta_title) > 200:
            raise ServicioError('meta_title no puede superar 200 caracteres.')
        post.meta_title = meta_title or None
    if meta_keywords != '':
        meta_keywords = meta_keywords.strip()
        if len(meta_keywords) > 300:
            raise ServicioError('meta_keywords no puede superar 300 caracteres.')
        post.meta_keywords = meta_keywords or None
    if meta_description != '':
        meta_description = meta_description.strip()
        if len(meta_description) > 500:
            raise ServicioError('meta_description no puede superar 500 caracteres.')
        post.meta_description = meta_description or None
    if activo is not None:
        post.activo = bool(activo)
    post.modified_by = usuario
    with transaction.atomic():
        post.save()
        if pais:
            adapter.asignar(post, modelo='post', pais=pais)
        if categorias is not None:
            post.categorias.set(_resolver_categorias(categorias))
    return _detalle_post(post)


def activar_post(identificador: str) -> dict:
    return actualizar_post(identificador, activo=True)


def desactivar_post(identificador: str) -> dict:
    return actualizar_post(identificador, activo=False)


def eliminar_post(identificador: str, confirmacion: bool = False) -> dict:
    if not confirmacion:
        raise ServicioError(
            'Para borrar el post de forma permanente debes pasar confirmacion=true.'
        )
    usuario_mcp()
    post = _obtener_post(identificador)
    post_id = post.id
    titulo = post.titulo
    slug = post.slug
    with transaction.atomic():
        post.delete()
    return {
        'ok': True,
        'eliminado': True,
        'id': post_id,
        'titulo': titulo,
        'slug': slug,
    }


def agregar_contenido_post(
    identificador: str,
    contenido: str,
    orden: int = 0,
) -> dict:
    usuario = usuario_mcp()
    post = _obtener_post(identificador)
    contenido = contenido if contenido is not None else ''
    if not str(contenido).strip():
        raise ServicioError('El contenido es obligatorio.')
    try:
        orden = int(orden if orden not in (None, '') else 0)
    except (TypeError, ValueError):
        raise ServicioError('El orden debe ser un entero.') from None
    if orden <= 0:
        maximo = ContenidoBlog.objects.filter(post=post).aggregate(m=Max('orden'))['m']
        orden = int(maximo or 0) + 1
    bloque = ContenidoBlog.objects.create(
        post=post,
        contenido=contenido,
        orden=orden,
        created_by=usuario,
    )
    return {
        'ok': True,
        'contenido_id': bloque.id,
        'post_id': post.id,
        'orden': bloque.orden,
    }


def actualizar_contenido_post(
    contenido_id: int,
    contenido: str = '',
    orden: int | None = None,
) -> dict:
    usuario = usuario_mcp()
    bloque = _obtener_contenido(contenido_id)
    if contenido != '':
        if not str(contenido).strip():
            raise ServicioError('El contenido no puede quedar vacío.')
        bloque.contenido = contenido
    if orden is not None and orden != '':
        try:
            bloque.orden = int(orden)
        except (TypeError, ValueError):
            raise ServicioError('El orden debe ser un entero.') from None
    bloque.modified_by = usuario
    bloque.save()
    return {
        'ok': True,
        'contenido_id': bloque.id,
        'post_id': bloque.post_id,
        'orden': bloque.orden,
        'contenido': bloque.contenido or '',
    }


def eliminar_contenido_post(contenido_id: int) -> dict:
    usuario_mcp()
    bloque = _obtener_contenido(contenido_id)
    post_id = bloque.post_id
    cid = bloque.id
    bloque.delete()
    return {'ok': True, 'eliminado': True, 'contenido_id': cid, 'post_id': post_id}


def reordenar_contenidos_post(identificador: str, contenido_ids: list[int]) -> dict:
    usuario_mcp()
    post = _obtener_post(identificador)
    if not isinstance(contenido_ids, (list, tuple)) or not contenido_ids:
        raise ServicioError('contenido_ids debe ser una lista no vacía de ids.')
    ids = []
    for item in contenido_ids:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            raise ServicioError('Cada contenido_id debe ser un entero.') from None
    existentes = list(
        ContenidoBlog.objects.filter(post=post).values_list('id', flat=True)
    )
    if set(ids) != set(existentes) or len(ids) != len(existentes):
        raise ServicioError(
            'contenido_ids debe incluir exactamente todos los bloques del post.'
        )
    with transaction.atomic():
        for orden, cid in enumerate(ids, start=1):
            ContenidoBlog.objects.filter(pk=cid, post=post).update(orden=orden)
    return {
        'ok': True,
        'post_id': post.id,
        'contenido_ids': ids,
    }


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
    """Publicar o crear draft de un post en Facebook (Graph API)."""
    from blog.facebook_blog import publicar_post_facebook as _publicar

    usuario_mcp()
    post = _obtener_post(identificador)
    result = _publicar(
        post,
        titulo=titulo.strip() or None,
        descripcion=descripcion.strip() or None,
        primer_comentario=primer_comentario if primer_comentario.strip() else None,
        modo=modo or 'draft',
        dry_run=bool(dry_run),
        forzar=bool(forzar),
        incluir_link=bool(incluir_link),
    )
    if not result.get('success'):
        raise ServicioError(result.get('error') or 'Error al publicar en Facebook')
    return {'ok': True, **result}


def hacer_publico_post_facebook(
    identificador: str,
    primer_comentario: str = '',
) -> dict:
    """Pasar un draft de Facebook a público y comentar si aplica."""
    from blog.facebook_blog import hacer_publico_post_facebook as _hacer_publico

    usuario_mcp()
    post = _obtener_post(identificador)
    result = _hacer_publico(
        post,
        primer_comentario=primer_comentario if primer_comentario.strip() else None,
    )
    if not result.get('success'):
        raise ServicioError(result.get('error') or 'Error al hacer público en Facebook')
    return {'ok': True, **result}


def estado_facebook_post(identificador: str) -> dict:
    """Estado local de publicación Facebook del post (sin llamar a Graph)."""
    from blog.facebook_blog import estado_facebook_post as _estado

    usuario_mcp()
    post = _obtener_post(identificador)
    return _estado(post)
