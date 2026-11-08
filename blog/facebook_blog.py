"""
Orquestación de publicación de posts del blog en Facebook.

Usa core.facebook.FacebookClient. Estrategia única:
- Con imagen: foto unpublished + feed con attached_media
- Sin imagen: feed con mensaje (+ link del artículo)
- Primer comentario solo cuando el post queda público
- Default: modo draft (visible en Business Suite → Borradores)
"""

from __future__ import annotations

import logging

from django.conf import settings

from core.facebook import get_facebook_client

logger = logging.getLogger(__name__)

MODOS_VALIDOS = {'draft', 'public'}


def _base_url(base_url=None) -> str:
    if base_url:
        return str(base_url).rstrip('/')
    return (
        getattr(settings, 'SITE_URL', None)
        or getattr(settings, 'URL_BASE', None)
        or 'http://localhost:8000'
    ).rstrip('/')


def _blog_url(post, base_url: str) -> str:
    if hasattr(post, 'get_absolute_url'):
        return f"{base_url}{post.get_absolute_url()}"
    if hasattr(post, 'mi_url_relativa'):
        return f"{base_url}{post.mi_url_relativa()}"
    return f"{base_url}/blog/{post.slug}/"


def _imagen_url(post, base_url: str) -> str | None:
    imagen_url = None
    if hasattr(post, 'mi_imagen'):
        imagen_url = post.mi_imagen()
    elif getattr(post, 'imagen', None):
        imagen = post.imagen
        imagen_url = imagen.url if hasattr(imagen, 'url') else None

    if not imagen_url:
        return None
    if str(imagen_url).startswith(('http://', 'https://')):
        return imagen_url
    return f"{base_url}{imagen_url}"


def _armar_copy(post, titulo=None, descripcion=None, primer_comentario=None, *, blog_url: str, incluir_link: bool):
    titulo_final = (titulo if titulo is not None else (post.titulo or '')).strip()
    descripcion_default = (getattr(post, 'meta_description', None) or '') or ''
    descripcion_final = (descripcion if descripcion is not None else descripcion_default).strip()

    if len(descripcion_final) > 2000:
        descripcion_final = descripcion_final[:1997] + '...'

    partes = [p for p in (titulo_final, descripcion_final) if p]
    mensaje = '\n\n'.join(partes)
    if incluir_link and blog_url and blog_url not in mensaje:
        mensaje = f"{mensaje}\n\n👇 {blog_url}".strip() if mensaje else blog_url

    if primer_comentario is None:
        comentario = f'🔗 Lee el artículo completo aquí: {blog_url}' if blog_url else ''
    else:
        comentario = str(primer_comentario).strip()

    return titulo_final, descripcion_final, mensaje, comentario


def _persistir_facebook(
    post,
    *,
    estado: str,
    post_id: str | None = None,
    permalink: str | None = None,
    titulo: str | None = None,
    descripcion: str | None = None,
    comentario: str | None = None,
):
    update_fields = []

    if hasattr(post, 'facebook_estado'):
        post.facebook_estado = estado
        update_fields.append('facebook_estado')

    publicado = estado == getattr(post, 'FACEBOOK_PUBLICO', 'publico')
    if hasattr(post, 'publicado_facebook'):
        post.publicado_facebook = publicado
        update_fields.append('publicado_facebook')

    if post_id is not None and hasattr(post, 'facebook_post_id'):
        post.facebook_post_id = post_id
        update_fields.append('facebook_post_id')

    if permalink is not None and hasattr(post, 'url_post_facebook'):
        post.url_post_facebook = permalink
        update_fields.append('url_post_facebook')

    if titulo is not None and hasattr(post, 'facebook_titulo_usado'):
        post.facebook_titulo_usado = titulo
        update_fields.append('facebook_titulo_usado')

    if descripcion is not None and hasattr(post, 'facebook_descripcion_usada'):
        post.facebook_descripcion_usada = descripcion
        update_fields.append('facebook_descripcion_usada')

    if comentario is not None and hasattr(post, 'facebook_comentario_usado'):
        post.facebook_comentario_usado = comentario
        update_fields.append('facebook_comentario_usado')

    if update_fields:
        post.save(update_fields=update_fields)


def _resolver_permalink(fb, post_id: str) -> str | None:
    ok, data = fb.get_permalink(post_id)
    if ok:
        return data.get('permalink_url')
    return None


def _comentar_si_aplica(fb, post_id: str, comentario: str) -> dict:
    if not comentario:
        return {'comment_success': False, 'comment_skipped': True, 'comment_response': {}}
    ok, data = fb.post_comment(post_id, comentario)
    if not ok:
        logger.error('Error al comentar post Facebook %s: %s', post_id, data.get('error'))
    return {
        'comment_success': ok,
        'comment_skipped': False,
        'comment_response': data,
        'comment_id': data.get('id') if ok else None,
    }


def estado_facebook_post(post) -> dict:
    """Resumen del estado Facebook del post (sin llamar a Graph)."""
    return {
        'ok': True,
        'post_id': post.id,
        'slug': getattr(post, 'slug', ''),
        'facebook_estado': getattr(post, 'facebook_estado', 'no_publicado'),
        'publicado_facebook': bool(getattr(post, 'publicado_facebook', False)),
        'facebook_post_id': getattr(post, 'facebook_post_id', None),
        'url_post_facebook': getattr(post, 'url_post_facebook', None),
        'facebook_titulo_usado': getattr(post, 'facebook_titulo_usado', None),
        'facebook_descripcion_usada': getattr(post, 'facebook_descripcion_usada', None),
        'facebook_comentario_usado': getattr(post, 'facebook_comentario_usado', None),
    }


def publicar_post_facebook(
    post,
    *,
    titulo=None,
    descripcion=None,
    primer_comentario=None,
    modo: str = 'draft',
    incluir_link: bool = True,
    forzar: bool = False,
    dry_run: bool = False,
    base_url=None,
) -> dict:
    """
    Publicar (o crear draft) de un Post en Facebook.

    Returns:
        dict con success, modo, dry_run, facebook_post_id, permalink, textos, errores, etc.
    """
    modo = (modo or 'draft').strip().lower()
    if modo not in MODOS_VALIDOS:
        return {
            'success': False,
            'error': f"modo inválido: {modo!r}. Use 'draft' o 'public'.",
        }

    estado_actual = getattr(post, 'facebook_estado', None)
    if estado_actual is None and getattr(post, 'publicado_facebook', False):
        estado_actual = 'publico'
    estado_actual = estado_actual or 'no_publicado'

    if estado_actual in ('draft', 'publico') and not forzar:
        return {
            'success': False,
            'error': (
                f"El post ya está en Facebook como '{estado_actual}'. "
                'Pasa forzar=True para crear uno nuevo, o usa hacer_publico_post_facebook si es draft.'
            ),
            'facebook_estado': estado_actual,
            'facebook_post_id': getattr(post, 'facebook_post_id', None),
            'url_post_facebook': getattr(post, 'url_post_facebook', None),
        }

    base = _base_url(base_url)
    blog_url = _blog_url(post, base)
    imagen_url = _imagen_url(post, base)
    titulo_f, descripcion_f, mensaje, comentario = _armar_copy(
        post,
        titulo,
        descripcion,
        primer_comentario,
        blog_url=blog_url,
        incluir_link=incluir_link,
    )

    localhost = 'localhost' in base or '127.0.0.1' in base
    payload_preview = {
        'modo': modo,
        'message': mensaje,
        'link': blog_url if incluir_link else None,
        'image_url': imagen_url,
        'primer_comentario': comentario if modo == 'public' else None,
        'primer_comentario_diferido': comentario if modo == 'draft' else None,
        'blog_url': blog_url,
        'base_url': base,
        'localhost_warning': bool(localhost),
    }

    if dry_run:
        return {
            'success': True,
            'dry_run': True,
            'modo': modo,
            'payload': payload_preview,
            'titulo': titulo_f,
            'descripcion': descripcion_f,
            'mensaje': mensaje,
            'primer_comentario': comentario,
        }

    if localhost:
        logger.warning(
            'SITE_URL/URL_BASE parece local (%s). Facebook no podrá scrapear link/imagen.',
            base,
        )

    fb = get_facebook_client()
    ok_creds, creds_data = fb.validate_credentials()
    if not ok_creds:
        _persistir_facebook(post, estado='error')
        return {
            'success': False,
            'error': creds_data.get('error', 'Credenciales Facebook inválidas'),
            'response': creds_data,
        }

    try:
        if imagen_url:
            ok, response = fb.create_photo_post(
                imagen_url,
                mensaje,
                modo=modo,
                link=None,  # link va en el mensaje; attached_media + link a veces chocan
            )
        else:
            if modo == 'draft':
                ok, response = fb.create_draft_post(mensaje, link=blog_url if incluir_link else None)
            else:
                ok, response = fb.create_feed_post(
                    mensaje,
                    link=blog_url if incluir_link else None,
                    published=True,
                )
    except Exception as e:
        logger.exception('Error inesperado publicando en Facebook')
        _persistir_facebook(post, estado='error')
        return {'success': False, 'error': str(e)}

    if not ok:
        _persistir_facebook(post, estado='error')
        return {
            'success': False,
            'error': response.get('error', 'Error al publicar en Facebook'),
            'response': response,
        }

    post_id = response.get('id') or response.get('post_id')
    permalink = _resolver_permalink(fb, post_id) if post_id else None
    estado = 'publico' if modo == 'public' else 'draft'

    comment_info = {'comment_success': False, 'comment_skipped': True, 'comment_response': {}}
    if modo == 'public' and post_id and comentario:
        comment_info = _comentar_si_aplica(fb, post_id, comentario)

    _persistir_facebook(
        post,
        estado=estado,
        post_id=post_id,
        permalink=permalink,
        titulo=titulo_f,
        descripcion=descripcion_f,
        comentario=comentario if modo == 'public' else (comentario or None),
    )

    return {
        'success': True,
        'dry_run': False,
        'modo': modo,
        'facebook_estado': estado,
        'facebook_post_id': post_id,
        'permalink': permalink,
        'url_post_facebook': permalink,
        'photo_id': response.get('photo_id'),
        'response': response,
        'titulo': titulo_f,
        'descripcion': descripcion_f,
        'mensaje': mensaje,
        'primer_comentario': comentario,
        **comment_info,
        'localhost_warning': bool(localhost),
    }


def hacer_publico_post_facebook(post, *, primer_comentario=None) -> dict:
    """Publicar un draft existente (o marcar público) y opcionalmente comentar."""
    estado = getattr(post, 'facebook_estado', 'no_publicado')
    post_id = getattr(post, 'facebook_post_id', None)

    if estado == 'publico' and post_id:
        return {
            'success': True,
            'already_public': True,
            'facebook_post_id': post_id,
            'url_post_facebook': getattr(post, 'url_post_facebook', None),
            'facebook_estado': 'publico',
        }

    if not post_id or estado not in ('draft', 'error'):
        return {
            'success': False,
            'error': (
                'No hay un draft de Facebook para publicar. '
                'Usa publicar_post_facebook(modo="draft") primero.'
            ),
            'facebook_estado': estado,
        }

    fb = get_facebook_client()
    ok, response = fb.publish_post(post_id)
    if not ok:
        _persistir_facebook(post, estado='error')
        return {
            'success': False,
            'error': response.get('error', 'No se pudo publicar el draft'),
            'response': response,
        }

    permalink = _resolver_permalink(fb, post_id) or getattr(post, 'url_post_facebook', None)

    if primer_comentario is None:
        comentario = getattr(post, 'facebook_comentario_usado', None) or ''
        if not comentario:
            base = _base_url()
            blog_url = _blog_url(post, base)
            comentario = f'🔗 Lee el artículo completo aquí: {blog_url}'
    else:
        comentario = str(primer_comentario).strip()

    comment_info = _comentar_si_aplica(fb, post_id, comentario) if comentario else {
        'comment_success': False,
        'comment_skipped': True,
        'comment_response': {},
    }

    _persistir_facebook(
        post,
        estado='publico',
        post_id=post_id,
        permalink=permalink,
        comentario=comentario or None,
    )

    return {
        'success': True,
        'facebook_estado': 'publico',
        'facebook_post_id': post_id,
        'permalink': permalink,
        'url_post_facebook': permalink,
        'response': response,
        'primer_comentario': comentario,
        **comment_info,
    }


# ---------------------------------------------------------------------------
# Compatibilidad con callers antiguos (admin / scripts)
# ---------------------------------------------------------------------------

def publicar_blog_facebook(blog_instance, base_url=None):
    """Deprecated: usa publicar_post_facebook(modo='public')."""
    result = publicar_post_facebook(
        blog_instance,
        modo='public',
        base_url=base_url,
    )
    return (
        result.get('success', False),
        result.get('response') or {'error': result.get('error')},
        result.get('comment_success', False),
        result.get('comment_response') or {},
    )


def publicar_blog_con_link(blog_instance, base_url=None):
    """Deprecated: delega al servicio único en modo public."""
    return publicar_blog_facebook(blog_instance, base_url=base_url)


def republicar_blog_facebook(blog_instance, base_url=None, forzar=False):
    """Deprecated: publicar_post_facebook(..., forzar=True, modo='public')."""
    result = publicar_post_facebook(
        blog_instance,
        modo='public',
        forzar=forzar,
        base_url=base_url,
    )
    return (
        result.get('success', False),
        result.get('response') or {'error': result.get('error')},
        result.get('comment_success', False),
        result.get('comment_response') or {},
    )


def auto_publicar_blog(sender, instance, created, **kwargs):
    """
    Signal opcional (NO registrado por defecto).

    Solo publica posts nuevos activos. Preferir acciones admin / MCP.
    """
    if not created:
        return
    if not getattr(instance, 'activo', False):
        return
    if getattr(instance, 'facebook_estado', 'no_publicado') in ('draft', 'publico'):
        return
    if getattr(instance, 'publicado_facebook', False):
        return
    try:
        result = publicar_post_facebook(instance, modo='draft')
        if result.get('success'):
            logger.info('Auto-draft Facebook OK: %s', instance.titulo)
        else:
            logger.error('Auto-draft Facebook falló: %s', result.get('error'))
    except Exception as e:
        logger.error('Error en auto_publicar_blog: %s', e)
