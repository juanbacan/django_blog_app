from django.contrib import sitemaps
from django.urls import reverse

from .models import Post

class PostSitemap(sitemaps.Sitemap):
    changefreq = "never"
    priority = 0.9

    def items(self):
        return Post.objects.filter(activo=True)

    # def lastmod(self, obj):
    #     return obj.modified_by

    def location(self, obj):
        return reverse('blog:post', args=[obj.slug])