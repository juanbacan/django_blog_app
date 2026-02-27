"""
Funciones para publicar automáticamente blogs en Facebook
"""

from django.conf import settings
from core.facebook import get_facebook_client
import logging

logger = logging.getLogger(__name__)

def publicar_blog_facebook(blog_instance, base_url=None):
    """
    Publica un blog en Facebook con imagen y texto, luego comenta con la URL
    
    Args:
        blog_instance: Instancia del modelo Blog
        base_url: URL base del sitio (opcional, se puede configurar en settings)
    
    Returns:
        tuple: (success, response_data, comment_success, comment_data)
    """
    try:
        # Obtener cliente de Facebook
        fb = get_facebook_client()
        
        # Construir URL del blog
        if not base_url:
            # Intentar obtener de settings o usar una por defecto
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        # Usar get_absolute_url si está disponible
        if hasattr(blog_instance, 'get_absolute_url'):
            blog_url = f"{base_url}{blog_instance.get_absolute_url()}"
        else:
            blog_url = f"{base_url}/blog/{blog_instance.slug}/"
        
        # Preparar el contenido para Facebook
        texto_post = blog_instance.meta_description or blog_instance.titulo
        
        # Truncar texto si es muy largo (Facebook tiene límites)
        if len(texto_post) > 400:
            texto_post = texto_post[:397] + "..."
        
        # Agregar call-to-action al texto
        texto_completo = f"📰 {texto_post}\n\n👉 Lee el artículo completo en el enlace de los comentarios."
        
        post_success = False
        post_response = {}
        comment_success = False
        comment_response = {}
        
        # Obtener imagen del blog (usando el método mi_imagen si existe)
        imagen_url = None
        if hasattr(blog_instance, 'mi_imagen'):
            imagen_url = blog_instance.mi_imagen()
        elif hasattr(blog_instance, 'imagen') and blog_instance.imagen:
            imagen_url = blog_instance.imagen.url if hasattr(blog_instance.imagen, 'url') else None
        
        # Publicar según si tiene imagen o no
        if imagen_url:
            # Construir URL completa de la imagen
            if imagen_url.startswith('http'):
                imagen_url_completa = imagen_url
            else:
                imagen_url_completa = f"{base_url}{imagen_url}"
            
            logger.info(f"Publicando blog con imagen: {imagen_url_completa}")
            
            # Publicar foto con caption
            post_success, post_response = fb.post_photo(
                image_url=imagen_url_completa,
                caption=texto_completo
            )
        else:
            logger.info("Publicando blog como texto simple")
            
            # Publicar solo texto
            post_success, post_response = fb.post_message(texto_completo)
        
        if post_success:
            # Obtener el ID correcto para comentarios
            # Para fotos, Facebook devuelve 'id' (foto) y 'post_id' (post real)
            # Para comentarios necesitamos el 'post_id'
            post_id = post_response.get('post_id') or post_response.get('id')
            photo_id = post_response.get('id')  # ID de la foto para la URL
            
            logger.info(f"Blog publicado exitosamente en Facebook. Post ID: {post_id}, Photo ID: {photo_id}")
            
            # Actualizar el modelo blog con la información del post (solo si tiene estos campos)
            if hasattr(blog_instance, 'publicado_facebook'):
                blog_instance.publicado_facebook = True
                # Usar el post_id para la URL (es más estable)
                blog_instance.url_post_facebook = f"https://www.facebook.com/{post_id.replace('_', '/posts/')}" if '_' in str(post_id) else f"https://www.facebook.com/{post_id}"
                blog_instance.save(update_fields=['publicado_facebook', 'url_post_facebook'])
            
            # Comentar con la URL del blog usando el post_id correcto
            comment_text = f"🔗 Lee el artículo completo aquí: {blog_url}\n\n#Blog #Educación"
            
            logger.info(f"Intentando comentar en post: {post_id}")
            comment_success, comment_response = fb.post_comment(post_id, comment_text)
            
            if comment_success:
                logger.info(f"Comentario con URL agregado exitosamente: {comment_response.get('id')}")
            else:
                logger.error(f"Error al agregar comentario: {comment_response.get('error')}")
        else:
            logger.error(f"Error al publicar blog en Facebook: {post_response.get('error')}")
        
        return post_success, post_response, comment_success, comment_response
        
    except Exception as e:
        logger.error(f"Error inesperado al publicar blog en Facebook: {e}")
        return False, {"error": str(e)}, False, {"error": str(e)}

def publicar_blog_con_link(blog_instance, base_url=None):
    """
    Alternativa: Publica el blog usando post_link en lugar de imagen
    Útil cuando hay problemas con URLs de imagen
    """
    try:
        fb = get_facebook_client()
        
        if not base_url:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        # Usar get_absolute_url si está disponible
        if hasattr(blog_instance, 'get_absolute_url'):
            blog_url = f"{base_url}{blog_instance.get_absolute_url()}"
        else:
            blog_url = f"{base_url}/blog/{blog_instance.slug}/"
        
        # Texto para el post
        texto_post = blog_instance.meta_description or blog_instance.titulo
        if len(texto_post) > 400:
            texto_post = texto_post[:397] + "..."
        
        mensaje = f"📰 {blog_instance.titulo}\n\n{texto_post}\n\n👇 Lee más en el enlace"
        
        # Publicar con enlace
        post_success, post_response = fb.post_link(
            message=mensaje,
            link=blog_url
        )
        
        if post_success:
            post_id = post_response.get('id')
            
            # Actualizar modelo (solo si tiene estos campos)
            if hasattr(blog_instance, 'publicado_facebook'):
                blog_instance.publicado_facebook = True
                blog_instance.url_post_facebook = f"https://www.facebook.com/{post_id}"
                blog_instance.save(update_fields=['publicado_facebook', 'url_post_facebook'])
            
            logger.info(f"Blog publicado con enlace en Facebook: {post_id}")
        
        return post_success, post_response, False, {}
        
    except Exception as e:
        logger.error(f"Error al publicar blog con enlace: {e}")
        return False, {"error": str(e)}, False, {}

def republicar_blog_facebook(blog_instance, base_url=None, forzar=False):
    """
    Republica un blog que ya fue publicado anteriormente
    
    Args:
        blog_instance: Instancia del modelo Blog
        base_url: URL base del sitio
        forzar: Si True, republica aunque ya esté marcado como publicado
    """
    # Verificar si ya fue publicado (solo si tiene el campo)
    if hasattr(blog_instance, 'publicado_facebook') and blog_instance.publicado_facebook and not forzar:
        logger.warning(f"El blog '{blog_instance.titulo}' ya fue publicado en Facebook")
        return False, {"error": "Ya fue publicado"}, False, {}
    
    # Resetear estado de publicación si se fuerza (solo si tiene estos campos)
    if forzar and hasattr(blog_instance, 'publicado_facebook'):
        blog_instance.publicado_facebook = False
        blog_instance.url_post_facebook = None
        blog_instance.save(update_fields=['publicado_facebook', 'url_post_facebook'])
    
    return publicar_blog_facebook(blog_instance, base_url)

# Función de conveniencia para usar en signals o admin actions
def auto_publicar_blog(sender, instance, created, **kwargs):
    """
    Signal para publicar automáticamente cuando se crea o actualiza un blog
    
    Para usar, agregar en apps.py o models.py:
    from django.db.models.signals import post_save
    from blog.models import Post
    from blog.facebook_blog import auto_publicar_blog
    
    post_save.connect(auto_publicar_blog, sender=Post)
    """
    # Solo publicar si el blog está activo y no ha sido publicado
    publicado = getattr(instance, 'publicado_facebook', False)
    if instance.activo and not publicado:
        try:
            success, response, comment_success, comment_response = publicar_blog_facebook(instance)
            
            if success:
                logger.info(f"Auto-publicación exitosa para blog: {instance.titulo}")
            else:
                logger.error(f"Error en auto-publicación: {response.get('error')}")
                
        except Exception as e:
            logger.error(f"Error en auto_publicar_blog signal: {e}")
