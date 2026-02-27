"""
Función para publicar posts del blog en WhatsApp
Adaptado para el proyecto quierosermaestro
"""

from django.conf import settings
import logging
import requests
import json

logger = logging.getLogger(__name__)


def _obtener_credenciales_whatsapp():
    """
    Helper para obtener credenciales de WhatsApp desde CredencialesAPI
    
    Returns:
        tuple: (credenciales, primer_canal, lista_canales) o (None, None, None) si hay error
    """
    try:
        from core.models import CredencialesAPI
        
        creds = CredencialesAPI.objects.first()
        if not creds:
            logger.error("No hay credenciales de API configuradas")
            return None, None, None
        
        # Validar configuración de Evolution API
        if not all([creds.evolution_api_url, creds.evolution_api_key, creds.evolution_instance_id]):
            logger.error("Configuración de WhatsApp incompleta en CredencialesAPI")
            return None, None, None
        
        # Obtener canales
        canales = []
        if creds.evolution_channels:
            try:
                canales = json.loads(creds.evolution_channels)
            except Exception as e:
                logger.error(f"Error parseando canales: {e}")
                return creds, None, []
        
        primer_canal = canales[0] if canales and len(canales) > 0 else None
        
        return creds, primer_canal, canales
        
    except Exception as e:
        logger.error(f"Error obteniendo credenciales de WhatsApp: {e}")
        return None, None, None


def publicar_blog_whatsapp_simple(post_instance, base_url=None, canal=None):
    """
    Publica un post en WhatsApp de forma simple: solo texto con URL
    
    Args:
        post_instance: Instancia del modelo Post
        base_url: URL base del sitio (opcional, se toma de settings)
        canal: Canal de WhatsApp (número en formato 593XXXXXXXXX@c.us) - se obtiene de CredencialesAPI si no se proporciona
    
    Returns:
        tuple: (success, response_data)
    """
    try:
        # Obtener credenciales y canal usando el helper
        creds, primer_canal, _ = _obtener_credenciales_whatsapp()
        
        if not creds:
            return False, {"error": "No hay credenciales de API configuradas"}
        
        # Si no se proporciona canal, usar el primero configurado
        if not canal:
            canal = primer_canal
            
        if not canal:
            logger.error("No hay canal de WhatsApp configurado en CredencialesAPI")
            return False, {"error": "No hay canal de WhatsApp configurado"}
        
        # Construir URL del post
        if not base_url:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        post_url = f"{base_url}{post_instance.get_absolute_url()}"
        
        # Preparar el mensaje simple
        titulo = post_instance.titulo or "Nuevo artículo"
        descripcion = post_instance.meta_description or ""
        
        # Mensaje simple: título, descripción y URL
        # WhatsApp no soporta HTML, usar formato texto plano con emojis
        if descripcion:
            mensaje = f"📰 *{titulo}*\n\n{descripcion}\n\n🔗 {post_url}"
        else:
            mensaje = f"📰 *{titulo}*\n\n🔗 {post_url}"
        
        # Truncar si es muy largo (WhatsApp tiene límite de ~4096 caracteres)
        if len(mensaje) > 4000:
            # Recortar la descripción para que quepa
            descripcion_max = 4000 - len(f"📰 *{titulo}*\n\n\n\n🔗 {post_url}") - 10
            if descripcion_max > 0:
                descripcion = descripcion[:descripcion_max] + "..."
                mensaje = f"📰 *{titulo}*\n\n{descripcion}\n\n🔗 {post_url}"
            else:
                # Solo título y URL si el título es muy largo
                mensaje = f"📰 *{titulo[:100]}...*\n\n🔗 {post_url}"
        
        logger.info(f"Publicando post en WhatsApp: {titulo[:50]}...")
        
        headers = {
            'Content-Type': 'application/json',
            'apikey': creds.evolution_api_key
        }
        
        payload = {
            'number': canal,
            'text': mensaje
        }
        
        logger.info(f"Enviando mensaje a Evolution API: {creds.evolution_api_url}/message/sendText/{creds.evolution_instance_id}")
        
        response = requests.post(
            f"{creds.evolution_api_url}/message/sendText/{creds.evolution_instance_id}",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            message_id = response_data.get('key', {}).get('id', 'sent')
            
            logger.info(f"Post publicado exitosamente en WhatsApp. Message ID: {message_id}")
            
            # Actualizar campos del post
            if hasattr(post_instance, 'publicado_whatsapp'):
                post_instance.publicado_whatsapp = True
                post_instance.whatsapp_message_id = message_id
                post_instance.whatsapp_channel = canal
                post_instance.save(update_fields=['publicado_whatsapp', 'whatsapp_message_id', 'whatsapp_channel'])
            
            return True, {
                'message_id': message_id,
                'canal': canal,
                'status': 'sent',
                'response': response_data
            }
        else:
            error_msg = f"Error al enviar mensaje por WhatsApp (Status: {response.status_code})"
            logger.error(f"{error_msg} - {response.text}")
            return False, {"error": error_msg, "details": response.text}
        
    except requests.RequestException as e:
        logger.error(f"Error de conexión al enviar WhatsApp: {e}")
        return False, {"error": f"Error de conexión: {str(e)}"}
    except Exception as e:
        logger.error(f"Error inesperado al publicar post en WhatsApp: {e}")
        return False, {"error": str(e)}


def publicar_blog_whatsapp_multiples_canales(post_instance, base_url=None, canales=None):
    """
    Publica un post en WhatsApp en múltiples canales
    
    Args:
        post_instance: Instancia del modelo Post
        base_url: URL base del sitio
        canales: Lista de canales (números en formato 593XXXXXXXXX@c.us) - se obtiene de CredencialesAPI si no se proporciona
    
    Returns:
        tuple: (success, response_data)
    """
    # Si no se proporcionan canales, obtenerlos usando el helper
    if not canales:
        creds, _, canales = _obtener_credenciales_whatsapp()
        
        if not creds:
            return False, {"error": "No hay credenciales de API configuradas"}
        
        if not canales:
            logger.warning(f"No hay canales configurados para el post: {post_instance.titulo}")
            return False, {"error": "No hay canales configurados"}
    
    success_results = []
    error_results = []
    
    # Enviar a cada canal
    for canal in canales:
        try:
            success, response = publicar_blog_whatsapp_simple(post_instance, base_url, canal)
            
            if success:
                success_results.append(f"✅ {canal}")
            else:
                error_results.append(f"❌ {canal}: {response.get('error', 'Error desconocido')}")
                
        except Exception as e:
            error_results.append(f"💥 {canal}: {str(e)}")
    
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


def auto_publicar_post_whatsapp(sender, instance, created, **kwargs):
    """
    Signal para publicar automáticamente cuando se crea un post
    
    Para usar, agregar en apps.py o models.py del blog:
    from django.db.models.signals import post_save
    from blog.models import Post
    from applications.main.whatsapp_post import auto_publicar_post_whatsapp
    
    post_save.connect(auto_publicar_post_whatsapp, sender=Post)
    """
    # Solo publicar si el post está activo y fue recién creado
    if created and instance.activo:
        try:
            success, response = publicar_blog_whatsapp_simple(instance)
            
            if success:
                logger.info(f"Auto-publicación en WhatsApp exitosa: {instance.titulo}")
            else:
                logger.error(f"Error en auto-publicación: {response.get('error')}")
                
        except Exception as e:
            logger.error(f"Error en auto_publicar_post_whatsapp signal: {e}")


# Funciones auxiliares

def formatear_numero_whatsapp(numero):
    """
    Formatea un número de teléfono al formato de WhatsApp
    
    Args:
        numero: Número en cualquier formato (con o sin +, espacios, guiones)
    
    Returns:
        str: Número en formato XXXXXXXXXXX@c.us o None si es inválido
    """
    if not numero:
        return None
    
    try:
        # Si ya está en formato @c.us o @g.us, devolverlo directamente
        if '@c.us' in numero or '@g.us' in numero:
            return numero
        
        # Limpiar el número
        numero_limpio = numero.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Verificar que solo tenga dígitos
        if numero_limpio.isdigit() and len(numero_limpio) >= 10:
            return f"{numero_limpio}@c.us"
        
        logger.warning(f"Número inválido: {numero}")
        return None
        
    except Exception as e:
        logger.error(f"Error formateando número WhatsApp: {e}")
        return None


def extraer_id_grupo_whatsapp(url_grupo):
    """
    Extrae el ID del grupo de WhatsApp desde diferentes formatos de URL
    
    Args:
        url_grupo: URL del grupo de WhatsApp
    
    Returns:
        str: ID del grupo o None si no se puede extraer
    """
    if not url_grupo:
        return None
    
    try:
        url_grupo = url_grupo.strip()
        
        # Si ya está en formato @g.us, devolverlo directamente
        if '@g.us' in url_grupo:
            return url_grupo
        
        # Si es una URL de chat.whatsapp.com
        if 'chat.whatsapp.com' in url_grupo:
            # Extraer el código del grupo
            codigo = url_grupo.split('/')[-1].strip()
            if codigo and len(codigo) > 10:
                # Para grupos necesitarías obtener el ID real mediante la API
                # Este es solo el código de invitación
                logger.warning(f"URL de grupo detectada: {url_grupo}. Necesitas obtener el ID real del grupo mediante la API")
                return codigo
        
        logger.warning(f"No se pudo extraer ID del grupo desde: {url_grupo}")
        return None
        
    except Exception as e:
        logger.error(f"Error extrayendo ID de grupo WhatsApp: {e}")
        return None
