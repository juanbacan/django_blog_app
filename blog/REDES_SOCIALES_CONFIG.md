# Configuración de Publicación en Redes Sociales

Este documento explica cómo configurar la publicación automática de blogs en Facebook, WhatsApp y Telegram.

## 📋 Requisitos Previos

### 1. Configurar `secrets.json`

Asegúrate de tener todas las variables configuradas en `secrets.json`:

```json
{
    "URL_BASE": "http://localhost:8000",
    
    "FACEBOOK_API_VERSION": "v23.0",
    "FACEBOOK_TIMEOUT": 30,
    "FACEBOOK_RATE_LIMIT": 200,

    "WHATSAPP_API_URL": "https://your-evolution-api.com",
    "WHATSAPP_API_KEY": "your-api-key-here",
    "WHATSAPP_INSTANCE": "your-instance-name",
    "WHATSAPP_NUMERO_DESTINO": "593XXXXXXXXX@c.us",

    "TELEGRAM_TIMEOUT": 30,
    "TELEGRAM_RATE_LIMIT": 30
}
```

### 2. Configurar Credenciales en el Admin

Las credenciales sensibles se almacenan en el modelo `CredencialesAPI` (en el admin de Django):

#### Facebook:
- `facebook_page_id`: ID de tu página de Facebook
- `facebook_token`: Token de acceso de tu página

#### WhatsApp (Evolution API):
- Configurar en `secrets.json` (ver arriba)

#### Telegram:
- `telegram_bot_token`: Token de tu bot de Telegram
- `telegram_default_chat_id`: ID del chat por defecto

---

## 🔧 Configuración por Plataforma

### 📘 Facebook

**1. Crear una App de Facebook:**
- Ve a [Facebook Developers](https://developers.facebook.com/)
- Crea una nueva app
- Agrega el producto "Facebook Login"

**2. Obtener Token de Página:**
```python
# En Graph API Explorer (https://developers.facebook.com/tools/explorer/)
# 1. Selecciona tu app
# 2. Genera un token de usuario con permisos:
#    - pages_manage_posts
#    - pages_read_engagement
# 3. Intercambia por token de página:
GET /me/accounts
```

**3. Configurar en Admin:**
- Page ID: El ID numérico de tu página
- Token: El token permanente de página

**4. Uso:**
```python
from blog.facebook_blog import publicar_blog_facebook

post = Post.objects.get(slug='mi-post')
success, response, comment_success, comment_response = publicar_blog_facebook(post)
```

---

### 💬 WhatsApp (Evolution API)

**1. Instalar Evolution API:**
```bash
# Opción 1: Docker
docker run -d \
  --name evolution-api \
  -p 8080:8080 \
  atendai/evolution-api

# Opción 2: Instalación manual
# Ver: https://github.com/EvolutionAPI/evolution-api
```

**2. Crear una Instancia:**
```bash
POST /instance/create
{
  "instanceName": "mi-instancia",
  "token": "tu-token-seguro",
  "qrcode": true
}
```

**3. Escanear QR y Conectar:**
- Obtén el QR: `GET /instance/qrcode/mi-instancia`
- Escanea con WhatsApp en tu teléfono
- Espera a que se conecte

**4. Configurar `secrets.json`:**
```json
{
    "WHATSAPP_API_URL": "http://localhost:8080",
    "WHATSAPP_API_KEY": "tu-token-seguro",
    "WHATSAPP_INSTANCE": "mi-instancia",
    "WHATSAPP_NUMERO_DESTINO": "593999999999@c.us"
}
```

**Formato de números:**
- Individual: `[código país][número]@c.us` → `593999999999@c.us`
- Grupo: `[group-id]@g.us` → `120363028XXXXXXXX@g.us`

**5. Uso:**
```python
from blog.whatsapp_blog_simple import publicar_blog_whatsapp_simple

post = Post.objects.get(slug='mi-post')
success, response = publicar_blog_whatsapp_simple(
    post, 
    numero_destino='593999999999@c.us'
)
```

---

### 🤖 Telegram

**1. Crear un Bot:**
- Habla con [@BotFather](https://t.me/BotFather) en Telegram
- Envía `/newbot`
- Sigue las instrucciones
- Guarda el token que te da

**2. Obtener Chat ID:**

**Para canal/grupo público:**
```bash
# Agrega el bot como administrador
# Envía un mensaje en el canal
# Luego:
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

**Para grupo privado/supergrupo:**
```bash
# Agrega el bot al grupo
# Envía un mensaje mencionando al bot
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
# Busca "chat":{"id":-1001234567890,...}
```

**3. Configurar en Admin:**
- `telegram_bot_token`: El token del BotFather
- `telegram_default_chat_id`: El ID del chat (número negativo para grupos)

**4. Para Foros/Topics:**
Si tu grupo tiene temas/topics habilitados, necesitas el `message_thread_id`:
```bash
# Envía un mensaje en el topic
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
# Busca "message_thread_id": 12345
```

**5. Uso:**
```python
from blog.telegram_post import publicar_blog_telegram

post = Post.objects.get(slug='mi-post')

# Simple
success, response = publicar_blog_telegram(post)

# Con chat específico
success, response = publicar_blog_telegram(
    post, 
    chat_id=-1001234567890
)

# Con topic/forum
success, response = publicar_blog_telegram(
    post, 
    chat_id=-1001234567890,
    thread_id=12345
)
```

---

## 🚀 Publicación Múltiple

### Publicar en todas las plataformas:
```python
from blog.facebook_blog import publicar_blog_facebook
from blog.whatsapp_blog_simple import publicar_blog_whatsapp_simple
from blog.telegram_post import publicar_blog_telegram

post = Post.objects.get(slug='mi-post')

# Facebook
fb_success, fb_response, fb_comment_success, fb_comment_response = publicar_blog_facebook(post)

# WhatsApp
wa_success, wa_response = publicar_blog_whatsapp_simple(post, numero_destino='593999999999@c.us')

# Telegram
tg_success, tg_response = publicar_blog_telegram(post)

print(f"Facebook: {'✅' if fb_success else '❌'}")
print(f"WhatsApp: {'✅' if wa_success else '❌'}")
print(f"Telegram: {'✅' if tg_success else '❌'}")
```

---

## 🔍 Verificar Estado de Publicación

Los campos del modelo `Post` se actualizan automáticamente:

```python
post = Post.objects.get(slug='mi-post')

print(f"Facebook: {post.publicado_facebook} - {post.url_post_facebook}")
print(f"WhatsApp: {post.publicado_whatsapp} - ID: {post.whatsapp_message_id}")
print(f"Telegram: {post.publicado_telegram} - URL: {post.url_post_telegram}")
```

---

## 🔄 Auto-publicación con Signals

Para publicar automáticamente cuando se crea un post:

```python
# En blog/apps.py
from django.apps import AppConfig

class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'
    
    def ready(self):
        from django.db.models.signals import post_save
        from blog.models import Post
        from blog.facebook_blog import auto_publicar_blog
        
        post_save.connect(auto_publicar_blog, sender=Post)
```

---

## ⚠️ Troubleshooting

### Facebook
- **Error de token expirado**: Tokens de usuario expiran, usa tokens de página permanentes
- **Permisos insuficientes**: Verifica que tienes `pages_manage_posts`
- **Imagen no se carga**: Asegúrate que la URL de imagen es pública

### WhatsApp
- **Error de conexión**: Verifica que Evolution API esté corriendo
- **QR expirado**: Regenera el QR si pasan más de 40 segundos
- **Número inválido**: Usa formato `[código][número]@c.us` sin espacios ni +

### Telegram
- **Bot no puede enviar**: Verifica que el bot sea administrador (para canales)
- **Chat ID incorrecto**: Recuerda que grupos tienen ID negativo
- **Topics no funcionan**: Asegúrate que el grupo tiene topics habilitados

---

## 📚 Recursos Adicionales

- [Facebook Graph API](https://developers.facebook.com/docs/graph-api/)
- [Evolution API Docs](https://doc.evolution-api.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

---

## 🆘 Soporte

Si algo no funciona, revisa los logs:
```bash
python manage.py shell
import logging
logging.basicConfig(level=logging.INFO)
```

Los módulos usan logging para reportar errores detallados.
