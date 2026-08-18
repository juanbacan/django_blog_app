import os, datetime
from PIL import Image
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils.functional import cached_property

from mptt.models import MPTTModel, TreeForeignKey
from tinymce import models as tinymce_models
from django_resized import ResizedImageField

from core.models import ModeloBase

from .managers import PostManager


class Categoria(MPTTModel):
    nombre = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    activo = models.BooleanField(default=True)

    class MPTTMeta:
        order_insertion_by = ['nombre']

    def __str__(self):
        full_path = [self.nombre]
        k = self.parent
        while k is not None:
            full_path.append(k.nombre)
            k = k.parent
        return ' -> '.join(full_path[::-1])
    
    @property
    def mis_posts(self):        
        # Esto obtiene los posts de esta categoría y de todas sus descendientes
        # Si no quieres incluir subcategorías, usa: return self.post_set.all().order_by('-fecha')[:5]
        return Post.objects.filter(categorias__in=self.get_descendants(include_self=True)).distinct().order_by('-fecha')[:5]
    
    

class Etiqueta(ModeloBase):
    nombre = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class Post(ModeloBase):
    titulo = models.TextField(max_length=500)
    fecha = models.DateTimeField(default=datetime.datetime.now)
    slug = models.SlugField(max_length=100, unique=True)
    categorias = models.ManyToManyField(Categoria)
    # etiquetas = models.ManyToManyField(Etiqueta)
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField('Destacado', default=False)
    meta_title = models.CharField(max_length=200, null=True, blank=True)
    meta_keywords = models.CharField(max_length=300, null=True, blank=True)
    meta_description = models.TextField(max_length=500, null=True, blank=True)
    
    # Campos para publicación en redes sociales
    # Facebook
    publicado_facebook = models.BooleanField(default=False, verbose_name="Publicado en Facebook")
    url_post_facebook = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL del post en Facebook")
    
    # WhatsApp
    publicado_whatsapp = models.BooleanField(default=False, verbose_name="Publicado en WhatsApp")
    whatsapp_message_id = models.CharField(max_length=255, null=True, blank=True, verbose_name="ID del mensaje de WhatsApp")
    whatsapp_channel = models.CharField(max_length=255, null=True, blank=True, verbose_name="Canal/Número de WhatsApp")
    
    # Telegram
    publicado_telegram = models.BooleanField(default=False, verbose_name="Publicado en Telegram")
    telegram_message_id = models.BigIntegerField(null=True, blank=True, verbose_name="ID del mensaje de Telegram")
    telegram_chat_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID del chat de Telegram")
    url_post_telegram = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL del post en Telegram")

    objects = PostManager()
    
    class Meta:
        ordering = ['-fecha']
        unique_together = ('slug', )

    def __str__(self):
        return self.titulo
    
    def mi_imagen(self):
        """Retorna la URL completa (absoluta) de la imagen."""
        try:
            from django.conf import settings
            
            imagen = self.imagenpost_set.filter(principal=True).first() or self.imagenpost_set.first()
            if not imagen:
                return None
                
            url = imagen.imagen.url
            if not url:
                return None
            
            # Si ya es URL absoluta, devolverla tal como está
            if url.startswith(('http://', 'https://')):
                return url
            
            # Si no, construir la URL completa usando SITE_URL de settings
            site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
            if site_url:
                return f"{site_url}{url}"
            
            return url
        except:
            return None


    def mis_descripciones(self):
        return self.contenidoblog_set.all().order_by('id')
    
    def mi_descripcion_corta(self):
        return self.meta_description or self.contenidoblog_set.order_by('orden').first().contenido or "Sin descripción"


    def mi_post_previo(self):
        post_previo = Post.objects.filter(fecha__lt=self.fecha).order_by('-fecha').first()
        if post_previo:
            return post_previo
        else:
            return None
        
    def mi_post_siguiente(self):
        post_siguiente = Post.objects.filter(fecha__gt=self.fecha).order_by('fecha').first()
        if post_siguiente:
            return post_siguiente
        else:
            return None
        
    def mis_posts_relacionados(self):
        return Post.objects.filter(categorias__in=self.categorias.all()).exclude(id=self.id).distinct()[:3]
    

    def mi_url_relativa(self):
        return '/post/' + self.slug + '/'

    @cached_property
    def mi_url_absoluta(self):
        return f"{settings.URL_BASE}{self.mi_url_relativa()}"
    
    def get_absolute_url(self):
        return reverse('blog:post', args=[self.slug])


class ImagenPost(ModeloBase):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    imagen = ResizedImageField(force_format="WEBP", quality=75, upload_to='blog', null=True, blank=True)
    principal = models.BooleanField(default=False)

    def __str__(self):
        return self.post.titulo
    

class ContenidoBlog(ModeloBase):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    contenido = tinymce_models.HTMLField()
    orden = models.IntegerField(default=0)
    
    def __str__(self):
        return self.post.titulo
