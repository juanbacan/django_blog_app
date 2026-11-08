# Configuración de Publicación en Redes Sociales

Publicación de posts del blog en Facebook, WhatsApp y Telegram.

## Arquitectura

| Capa | Responsabilidad |
|------|-----------------|
| `core.facebook.FacebookClient` | Graph API (Pages: feed, fotos, drafts, comentarios, likes, diagnóstico) |
| `blog.facebook_blog` | Orquestación sobre el modelo `Post` |
| Admin / MCP | Misma API de servicio |

## secrets.json

```json
{
    "URL_BASE": "https://tudominio.com",
    "FACEBOOK_API_VERSION": "v23.0",
    "FACEBOOK_TIMEOUT": 30,
    "FACEBOOK_RATE_LIMIT": 200,
    "TELEGRAM_TIMEOUT": 30,
    "TELEGRAM_RATE_LIMIT": 30
}
```

`SITE_URL` en settings debe ser alias de `URL_BASE` (URL **pública https**). Con `localhost` Facebook no puede scrapear link/imagen.

## Credenciales (admin → CredencialesAPI)

### Facebook
- `facebook_page_id`: ID de la Page
- `facebook_token`: Page access token (TextField; tokens largos OK). Permisos: `pages_manage_posts`, `pages_read_engagement`, `pages_manage_engagement`

### Telegram
- `telegram_bot_token`
- `telegram_default_chat_id`

### WhatsApp (Evolution)
También configurable en `CredencialesAPI` / secrets según el host.

---

## Facebook — flujo unificado

Estrategia única:
1. Si hay imagen → foto unpublished + `/feed` con `attached_media`
2. Si no → `/feed` con mensaje (+ link del artículo)
3. Primer comentario **solo** cuando el post queda público

### Modos

| modo | Efecto |
|------|--------|
| `draft` (default) | `published=false` + `unpublished_content_type=DRAFT` → visible en Business Suite → Borradores |
| `public` | Publicación en vivo + comentario |

### Servicio

```python
from blog.facebook_blog import (
    publicar_post_facebook,
    hacer_publico_post_facebook,
    estado_facebook_post,
)

post = Post.objects.get(slug='mi-post')

# 1) Revisar sin llamar a Graph
preview = publicar_post_facebook(post, dry_run=True, modo='draft')

# 2) Crear borrador (revisar en Business Suite)
result = publicar_post_facebook(
    post,
    titulo='Hook opcional',
    descripcion='Cuerpo opcional',
    primer_comentario='Comentario para cuando sea público',
    modo='draft',
)

# 3) Pasar a público + comentar
hacer_publico_post_facebook(post)

# Forzar un post NUEVO aunque ya exista uno asociado
publicar_post_facebook(post, modo='public', forzar=True)
```

### Campos del modelo `Post`

- `facebook_estado`: `no_publicado` | `draft` | `publico` | `error`
- `facebook_post_id`, `url_post_facebook`
- `facebook_titulo_usado`, `facebook_descripcion_usada`, `facebook_comentario_usado`
- `publicado_facebook`: `True` solo si `facebook_estado == publico` (compat)

### Admin

Acciones:
- **Facebook: crear borrador (draft)** — form intermedio con título/descripcion/comentario si hay 1 post
- **Facebook: publicar público**
- **Facebook: hacer público (desde draft)**
- **Facebook: publicar de nuevo (forzar)**
- **Publicar en TODAS las redes** — Facebook en **draft**; Telegram/WhatsApp como siempre

No hay “republicar” con otra estrategia distinta.

### MCP

- `publicar_post_facebook(identificador, titulo='', descripcion='', primer_comentario='', modo='draft', dry_run=false, forzar=false, incluir_link=true)`
- `hacer_publico_post_facebook(identificador, primer_comentario='')`
- `estado_facebook_post(identificador)`

### Auto-publish

`auto_publicar_blog` **no está registrado** por defecto. Solo para signals explícitos (y solo en `created` + `activo` → draft).

---

## WhatsApp

```python
from blog.whatsapp_blog import publicar_blog_whatsapp_simple

success, response = publicar_blog_whatsapp_simple(post)
```

## Telegram

```python
from blog.telegram_blog import publicar_blog_telegram

success, response = publicar_blog_telegram(post)
# o con chat_id / thread_id
```

---

## Checklist de verificación Facebook

1. Credenciales Page token + page id en admin (`CredencialesAPI`)
2. `URL_BASE` https público en secrets
3. `publicar_post_facebook(..., dry_run=True)` → payload sin llamar a Meta
4. `modo='draft'` → aparece en Business Suite → Contenido → Borradores
5. `hacer_publico_post_facebook` → live + primer comentario
6. Permalink guardado en `url_post_facebook`
7. Token > 255 caracteres no se trunca
8. Cambiar token en admin y publicar **sin** reiniciar el proceso

---

## Troubleshooting

### Facebook
- Token expirado / code 190: renovar page token; el cliente refresca credenciales y reintenta una vez
- Draft no visible en Business Suite: falta `unpublished_content_type=DRAFT`
- Imagen/link no cargan: `URL_BASE` debe ser público https
- Comentario en draft: no se envía; se aplica al hacer público

### WhatsApp
- Evolution API arriba, QR conectado, formato `593...@c.us` o grupo `@g.us`

### Telegram
- Bot admin del canal/grupo; chat_id negativo en grupos

## Recursos

- [Facebook Graph API](https://developers.facebook.com/docs/graph-api/)
- [Pages posts](https://developers.facebook.com/documentation/pages-api/posts)
- [Evolution API](https://doc.evolution-api.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
