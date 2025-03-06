from django.db import models

class PostManager(models.Manager):

    def ultimas_noticias(self):
        return self.filter(activo=True).order_by('-fecha')[:6]

    def locales(self):
        return self.filter(activo=True, categorias__slug='local').order_by('-fecha')[:5]
    
    def nacionales(self):
        return self.filter(activo=True, categorias__slug='nacionales').order_by('-fecha')[:5]
    
    def internacionales(self):
        return self.filter(activo=True, categorias__slug='internacionales').order_by('-fecha')[:5]
    
    def deportes(self):
        return self.filter(activo=True, categorias__slug='deportes').order_by('-fecha')[:5]