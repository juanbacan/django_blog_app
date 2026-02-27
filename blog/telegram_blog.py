"""
Funciones para publicar automáticamente blogs en Telegram.

- Por defecto envía SOLO el enlace del blog (solo_enlace=True) para que Telegram
  genere automáticamente la vista previa con la imagen de Open Graph.
- Si se establece solo_enlace=False, usa la lógica extendida:
  - Si hay imagen en el Blog: envía sendPhoto con caption.
  - Si no hay imagen: envía mensaje de texto con enlace y vista previa.

Requisitos:
- Contar con un Singleton TelegramClient y el helper get_telegram_client:
    from applications.core.telegram import get_telegram_client

Campos opcionales en tu modelo Blog (si existen se actualizarán):
- publicado_telegram: bool
- telegram_message_id: int
- telegram_chat_id: int/str
- url_post_telegram: str (no se calcula automáticamente para foros/privados)
"""

import logging
from typing import Optional, Tuple, Dict, Any
from django.conf import settings

# Asegúrate de tener el Singleton disponible en este import:
# applications/core/telegram.py define get_telegram_client()
from core.telegram import get_telegram_client

logger = logging.getLogger(__name__)


def _truncar(texto: str, limite: int) -> str:
    if not texto:
        return ""
    if len(texto) <= limite:
        return texto
    return texto[: max(0, limite - 3)] + "..."


def _build_base_url(_default: str = "http://localhost:8000") -> str:
    """
    Retorna la URL base del sitio sin slash final.
    Toma primero settings.SITE_URL si existe.
    """
    base_url = getattr(settings, "SITE_URL", _default) or _default
    return base_url.rstrip("/")


def _blog_url(base_url: str, blog_instance) -> str:
    """
    Construye la URL canónica del blog usando get_absolute_url si está disponible.
    """
    if hasattr(blog_instance, 'get_absolute_url'):
        return f"{base_url}{blog_instance.get_absolute_url()}"
    return f"{base_url}/blog/{blog_instance.slug}/"


def _update_blog_fields(
    blog_instance,
    publicado_telegram: Optional[bool] = None,
    telegram_message_id: Optional[int] = None,
    telegram_chat_id: Optional[int] = None,
    url_post_telegram: Optional[str] = None,
) -> None:
    """
    Actualiza de forma segura los campos del Blog si existen.
    """
    try:
        changed = False
        if publicado_telegram is not None and hasattr(blog_instance, "publicado_telegram"):
            blog_instance.publicado_telegram = publicado_telegram
            changed = True
        if telegram_message_id is not None and hasattr(blog_instance, "telegram_message_id"):
            blog_instance.telegram_message_id = telegram_message_id
            changed = True
        if telegram_chat_id is not None and hasattr(blog_instance, "telegram_chat_id"):
            blog_instance.telegram_chat_id = telegram_chat_id
            changed = True
        if url_post_telegram is not None and hasattr(blog_instance, "url_post_telegram"):
            blog_instance.url_post_telegram = url_post_telegram
            changed = True

        if changed:
            # Detecta qué campos existen realmente para update_fields
            campos = [f.name for f in getattr(blog_instance, "_meta").fields]
            to_update = [
                c
                for c in ["publicado_telegram", "telegram_message_id", "telegram_chat_id", "url_post_telegram"]
                if c in campos
            ]
            blog_instance.save(update_fields=to_update)
    except Exception as e:
        logger.warning(f"Publicado en Telegram, pero no se pudo actualizar el modelo: {e}")


def publicar_blog_telegram(
    blog_instance,
    base_url: Optional[str] = None,
    chat_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Publica un blog en Telegram de forma simple: solo texto con URL
    Telegram se encarga de generar la vista previa automáticamente
    
    Args:
        blog_instance: Instancia del modelo Blog (campos usados: slug, titulo, meta_description).
        base_url: URL base del sitio (por defecto settings.SITE_URL).
        chat_id: ID del chat destino. Si no se pasa, usa el configurado en CredencialesAPI.
        thread_id: ID del topic si el grupo es foro y deseas publicar en un tema concreto.

    Returns:
        (success, response)
    """
    try:
        tg = get_telegram_client()

        base = _build_base_url(base_url or "http://localhost:8000")
        blog_url = _blog_url(base, blog_instance)

        # Preparar el mensaje simple: título, descripción y URL
        titulo = blog_instance.titulo or "Nuevo artículo"
        descripcion = blog_instance.meta_description or ""
        
        if descripcion:
            mensaje = f"📰 <b>{titulo}</b>\n\n{descripcion}\n\n🔗 {blog_url}"
        else:
            mensaje = f"📰 <b>{titulo}</b>\n\n🔗 {blog_url}"
        
        # Truncar si es muy largo (Telegram tiene límite de ~4096 caracteres)
        if len(mensaje) > 4000:
            # Recortar la descripción para que quepa
            descripcion_max = 4000 - len(f"📰 <b>{titulo}</b>\n\n\n\n🔗 {blog_url}") - 10
            if descripcion_max > 0:
                descripcion = descripcion[:descripcion_max] + "..."
                mensaje = f"📰 <b>{titulo}</b>\n\n{descripcion}\n\n🔗 {blog_url}"
            else:
                # Solo título y URL si el título es muy largo
                mensaje = f"📰 <b>{titulo[:100]}...</b>\n\n🔗 {blog_url}"

        logger.info(f"Publicando blog en Telegram: {titulo[:50]}...")

        # Enviar mensaje con vista previa habilitada
        ok, res = tg.send_message(
            text=mensaje,
            chat_id=chat_id,
            thread_id=thread_id,
            parse_mode="HTML",
            disable_web_page_preview=False,  # Permitir vista previa
            link_preview_options={
                "is_disabled": False,
                "prefer_large_media": True,
                "show_above_text": True,
            }
        )

        if ok:
            msg_id = res.get("message_id")
            chat_info = res.get("chat", {})
            chat_id_real = chat_info.get("id")

            # Si el grupo tiene username público y no es foro, construir URL pública:
            url_pub = None
            username = chat_info.get("username")
            if username and thread_id is None:
                try:
                    url_pub = f"https://t.me/{username}/{msg_id}"
                except Exception:
                    url_pub = None

            _update_blog_fields(
                blog_instance,
                publicado_telegram=True,
                telegram_message_id=msg_id,
                telegram_chat_id=chat_id_real,
                url_post_telegram=url_pub,
            )
            
            logger.info(f"Blog publicado exitosamente en Telegram. Message ID: {msg_id}")
        else:
            logger.error(f"Error al publicar blog en Telegram: {res.get('error')}")

        return ok, res

    except Exception as e:
        logger.error(f"Error inesperado al publicar blog en Telegram: {e}")
        return False, {"error": str(e)}


def republicar_blog_telegram(
    blog_instance,
    base_url: Optional[str] = None,
    chat_id: Optional[int] = None,
    thread_id: Optional[int] = None,
    forzar: bool = False,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Republica un blog en Telegram. Si ya está marcado como publicado_telegram y no se fuerza, no hace nada.
    """
    try:
        if getattr(blog_instance, "publicado_telegram", False) and not forzar:
            logger.warning(f"El blog '{blog_instance.titulo}' ya fue publicado en Telegram")
            return False, {"error": "Ya fue publicado"}

        if forzar:
            try:
                changed = False
                if hasattr(blog_instance, "publicado_telegram"):
                    blog_instance.publicado_telegram = False
                    changed = True
                if hasattr(blog_instance, "telegram_message_id"):
                    blog_instance.telegram_message_id = None
                    changed = True
                if hasattr(blog_instance, "telegram_chat_id"):
                    blog_instance.telegram_chat_id = None
                    changed = True
                if hasattr(blog_instance, "url_post_telegram"):
                    blog_instance.url_post_telegram = None
                    changed = True
                if changed:
                    blog_instance.save()
            except Exception as e:
                logger.warning(f"No se pudo limpiar estado previo de Telegram en el modelo: {e}")

        return publicar_blog_telegram(
            blog_instance=blog_instance,
            base_url=base_url,
            chat_id=chat_id,
            thread_id=thread_id,
        )
    except Exception as e:
        logger.error(f"Error en republicar_blog_telegram: {e}")
        return False, {"error": str(e)}


def auto_publicar_blog_telegram(sender, instance, created, **kwargs) -> None:
    """
    Signal para publicar automáticamente en Telegram cuando se crea/actualiza un blog.

    Uso sugerido:
        from django.db.models.signals import post_save
        from blog.models import Post
        from blog.telegram_post import auto_publicar_blog_telegram

        post_save.connect(auto_publicar_blog_telegram, sender=Post)
    """
    try:
        # Publica solo si el blog está activo y no se ha publicado aún en Telegram
        if getattr(instance, "activo", False) and not getattr(instance, "publicado_telegram", False):
            ok, res = publicar_blog_telegram(instance)
            if ok:
                logger.info(f"Auto-publicación en Telegram OK: {instance.titulo}")
            else:
                logger.error(f"Auto-publicación en Telegram falló: {res}")
    except Exception as e:
        logger.error(f"Error en auto_publicar_blog_telegram: {e}")


def publicar_blog_telegram_multiples_chats(
    blog_instance,
    base_url: Optional[str] = None,
    chat_ids: Optional[list] = None,
    thread_ids: Optional[Dict[int, int]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Publicar un blog en Telegram en múltiples chats/canales.
    
    Args:
        blog_instance: Instancia del modelo Blog/Post
        base_url: URL base del sitio (opcional, se toma de settings)
        chat_ids: Lista de IDs de chats donde publicar (opcional, usa TELEGRAM_CHAT_IDS de settings)
        thread_ids: Diccionario {chat_id: thread_id} para foros (opcional)
        
    Returns:
        tuple: (success, response_data)
    """
    success_results = []
    error_results = []
    
    try:
        # Si no se proporcionan chat_ids, obtener de settings
        if not chat_ids:
            chat_ids = getattr(settings, 'TELEGRAM_CHAT_IDS', [])
            if not chat_ids:
                # Usar el chat por defecto
                tg = get_telegram_client()
                if tg.default_chat_id:
                    chat_ids = [tg.default_chat_id]
        
        if not chat_ids:
            return False, {"error": "No hay chats configurados para publicar"}
        
        # Asegurar que chat_ids sea una lista
        if not isinstance(chat_ids, list):
            chat_ids = [chat_ids]
        
        # Obtener thread_ids si no se proporcionan
        if thread_ids is None:
            thread_ids = {}
        
        # Publicar en cada chat
        for chat_id in chat_ids:
            try:
                thread_id = thread_ids.get(chat_id) if isinstance(thread_ids, dict) else None
                success, response = publicar_blog_telegram(
                    blog_instance, base_url, chat_id, thread_id
                )
                
                if success:
                    chat_info = response.get('chat', {})
                    chat_title = chat_info.get('title', f'ID: {chat_id}')
                    thread_info = f" (Thread: {thread_id})" if thread_id else ""
                    success_results.append(f"✅ {chat_title}{thread_info}")
                else:
                    error_results.append(f"❌ Chat {chat_id}: {response.get('error', 'Error desconocido')}")
                    
            except Exception as e:
                error_results.append(f"💥 Chat {chat_id}: {str(e)}")
        
        # Preparar respuesta final
        total_success = len(success_results)
        total_errors = len(error_results)
        
        response = {
            "total_success": total_success,
            "total_errors": total_errors,
            "success_results": success_results,
            "error_results": error_results
        }
        
        # Considerar exitoso si al menos uno funcionó
        overall_success = total_success > 0
        
        return overall_success, response
        
    except Exception as e:
        logger.error(f"Error inesperado en publicar_blog_telegram_multiples_chats: {e}")
        return False, {"error": str(e), "success_results": success_results, "error_results": error_results}
