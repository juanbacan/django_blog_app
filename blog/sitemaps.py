from django.contrib import sitemaps
from django.urls import reverse

from .models import Post, Categoria

class PostsSitemap(sitemaps.Sitemap):
    priority = 0.9
    changefreq = 'weekly'

    def items(self):
        return [
            'blog:posts'
        ]

    def location(self, item):
        return reverse(item)
    

class PostsCategoriaSitemap(sitemaps.Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return Categoria.objects.all()

    def location(self, obj):
        return reverse('blog:posts_categoria', kwargs={'categoria': obj.slug})


class PostSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Post.objects.filter(activo=True)

    def location(self, obj):
        return reverse('blog:post', args=[obj.slug])