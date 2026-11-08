"""Resolución de imágenes para el blog MCP (URL, base64 o clave R2)."""

from __future__ import annotations

import base64
import binascii
import re
import uuid
from urllib.parse import urlparse

from django.conf import settings

BLOG_UPLOAD_PREFIX = 'blog-uploads'
ALLOWED_IMAGE_CONTENT_TYPES = frozenset({
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/gif',
})
DATA_URI_RE = re.compile(
    r'^data:(?P<content_type>image/[\w.+-]+);base64,(?P<data>.+)$',
    re.DOTALL,
)


def _r2_option(name: str, fallback_setting: str = '') -> str:
    storages = getattr(settings, 'STORAGES', None) or {}
    options = (storages.get('default') or {}).get('OPTIONS') or {}
    mapping = {
        'access_key': 'AWS_S3_ACCESS_KEY_ID',
        'secret_key': 'AWS_S3_SECRET_ACCESS_KEY',
        'bucket_name': 'AWS_STORAGE_BUCKET_NAME',
        'endpoint_url': 'AWS_S3_ENDPOINT_URL',
        'custom_domain': 'AWS_S3_CUSTOM_DOMAIN',
        'region_name': 'AWS_S3_REGION_NAME',
    }
    setting_name = fallback_setting or mapping.get(name, '')
    valor = options.get(name) or (getattr(settings, setting_name, None) if setting_name else None)
    return str(valor or '').strip()


def r2_configured() -> bool:
    return all([
        _r2_option('endpoint_url'),
        _r2_option('access_key'),
        _r2_option('secret_key'),
        _r2_option('bucket_name'),
    ])


def build_r2_client():
    if not r2_configured():
        raise ValueError(
            'Cloudflare R2 no está configurado (activa R2_MEDIA_ENABLED y las claves AWS_S3_*).'
        )
    import boto3
    from botocore.config import Config

    return boto3.client(
        's3',
        endpoint_url=_r2_option('endpoint_url'),
        aws_access_key_id=_r2_option('access_key'),
        aws_secret_access_key=_r2_option('secret_key'),
        region_name=_r2_option('region_name') or 'auto',
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
    )


def r2_public_url(key: str) -> str:
    key = (key or '').lstrip('/')
    custom_domain = _r2_option('custom_domain')
    if custom_domain:
        return f'https://{custom_domain.rstrip("/")}/{key}'
    endpoint = _r2_option('endpoint_url').rstrip('/')
    bucket = _r2_option('bucket_name')
    return f'{endpoint}/{bucket}/{key}'


def extract_r2_key_from_url(url: str) -> str | None:
    raw = (url or '').strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in ('http', 'https'):
        return None
    path = (parsed.path or '').lstrip('/')
    if not path:
        return None

    host = (parsed.netloc or '').lower()
    custom = _r2_option('custom_domain').lower().rstrip('/')
    if custom and host == custom:
        return path

    endpoint = _r2_option('endpoint_url')
    bucket = _r2_option('bucket_name')
    if endpoint and bucket:
        endpoint_host = urlparse(endpoint).netloc.lower()
        if host == endpoint_host:
            prefix = f'{bucket}/'
            if path.startswith(prefix):
                return path[len(prefix):]
            if path.startswith(f'{BLOG_UPLOAD_PREFIX}/') or path.startswith('blog/'):
                return path
    return None


def normalize_r2_key(value: str) -> str:
    texto = (value or '').strip()
    if not texto:
        return ''
    if texto.startswith(('http://', 'https://')):
        key = extract_r2_key_from_url(texto)
        if not key:
            raise ValueError(
                'imagen_r2_key parece una URL, pero no es de nuestro CDN/R2. '
                'Usa la clave (ej. blog-uploads/...) o imagen_url.'
            )
        return key
    return texto.lstrip('/')


def _safe_filename(filename: str) -> str:
    filename = (filename or 'imagen').strip().replace('\\', '/').rsplit('/', 1)[-1]
    filename = re.sub(r'[^A-Za-z0-9._-]+', '-', filename).strip('-._') or 'imagen'
    return filename[:120]


def _extension_for_content_type(content_type: str) -> str:
    return {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/gif': '.gif',
    }.get((content_type or '').lower(), '.jpg')


def generate_presigned_upload(filename: str, content_type: str) -> dict:
    content_type = (content_type or 'image/jpeg').strip().lower()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError(
            f'content_type no permitido. Usa uno de: {", ".join(sorted(ALLOWED_IMAGE_CONTENT_TYPES))}.'
        )
    safe_name = _safe_filename(filename)
    key = f'{BLOG_UPLOAD_PREFIX}/{uuid.uuid4().hex}-{safe_name}'
    client = build_r2_client()
    expires_in = 900
    upload_url = client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': _r2_option('bucket_name'),
            'Key': key,
            'ContentType': content_type,
        },
        ExpiresIn=expires_in,
    )
    return {
        'upload_url': upload_url,
        'method': 'PUT',
        'key': key,
        'public_url': r2_public_url(key),
        'content_type': content_type,
        'expires_in': expires_in,
    }


def fetch_bytes_from_r2_key(key: str) -> tuple[str, bytes]:
    from botocore.exceptions import ClientError

    key = normalize_r2_key(key)
    if not key:
        raise ValueError('imagen_r2_key no puede estar vacío.')
    if '..' in key.split('/'):
        raise ValueError('imagen_r2_key inválida.')

    client = build_r2_client()
    try:
        response = client.get_object(Bucket=_r2_option('bucket_name'), Key=key)
    except ClientError as exc:
        code = exc.response.get('Error', {}).get('Code', '')
        if code in ('NoSuchKey', '404', 'NotFound'):
            raise ValueError(f'No existe ningún archivo en R2 con la clave "{key}".') from exc
        raise ValueError(f'No se pudo leer imagen_r2_key desde R2: {exc}') from exc

    content_type = (response.get('ContentType') or '').split(';')[0].strip().lower()
    if content_type and not (
        content_type.startswith('image/')
        or content_type in ('application/octet-stream', 'binary/octet-stream')
    ):
        raise ValueError('imagen_r2_key no apunta a una imagen.')

    filename = _safe_filename(key.rsplit('/', 1)[-1])
    if '.' not in filename:
        filename = f'{filename}{_extension_for_content_type(content_type)}'
    elif content_type in ('application/octet-stream', 'binary/octet-stream', ''):
        ext = filename.rsplit('.', 1)[-1].lower()
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
            raise ValueError('imagen_r2_key no apunta a una imagen.')
    return filename, response['Body'].read()


def fetch_bytes_from_url(url: str) -> tuple[str, bytes]:
    import requests

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('imagen_url debe ser una URL http o https.')

    own_key = extract_r2_key_from_url(url)
    if own_key:
        return fetch_bytes_from_r2_key(own_key)

    response = requests.get(
        url,
        timeout=30,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; DjangoBlogMCP/1.0)',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        },
    )
    response.raise_for_status()
    content_type = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
    if content_type and not content_type.startswith('image/'):
        raise ValueError('imagen_url no apunta a una imagen válida.')

    filename = _safe_filename(parsed.path.rsplit('/', 1)[-1] or 'imagen')
    if '.' not in filename:
        filename = f'{filename}{_extension_for_content_type(content_type)}'
    return filename, response.content


def decode_base64_image(
    raw_value: str,
    filename: str | None = None,
    content_type: str | None = None,
) -> tuple[str, bytes]:
    raw_value = (raw_value or '').strip()
    if not raw_value:
        raise ValueError('imagen_base64 no puede estar vacío.')

    content_type = (content_type or '').strip().lower() or None
    payload = raw_value
    data_uri_match = DATA_URI_RE.match(raw_value)
    if data_uri_match:
        content_type = data_uri_match.group('content_type').lower()
        payload = data_uri_match.group('data').strip()

    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError('imagen_base64 no es válida.') from exc
    if not image_bytes:
        raise ValueError('imagen_base64 está vacía.')
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValueError(
            f'content_type de imagen no permitido. Usa uno de: {", ".join(sorted(ALLOWED_IMAGE_CONTENT_TYPES))}.'
        )

    safe_name = _safe_filename(filename or 'imagen-generada')
    if '.' not in safe_name:
        safe_name = f'{safe_name}{_extension_for_content_type(content_type)}'
    return safe_name, image_bytes


def resolve_image_bytes(image_payload: dict) -> tuple[str, bytes]:
    source = image_payload.get('source')
    if source == 'r2_key':
        return fetch_bytes_from_r2_key(image_payload['r2_key'])
    if source == 'base64':
        return decode_base64_image(
            image_payload['base64'],
            filename=image_payload.get('filename'),
            content_type=image_payload.get('content_type'),
        )
    if source == 'url':
        return fetch_bytes_from_url(image_payload['url'])
    raise ValueError('Fuente de imagen no soportada.')
