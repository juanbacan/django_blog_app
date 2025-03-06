from django.contrib import admin
from django import forms
from mptt.admin import MPTTModelAdmin, DraggableMPTTAdmin
from .models import Post, ContenidoBlog, Categoria, ImagenPost, Etiqueta
# Register your models here.

# admin.site.register(Categoria, MPTTModelAdmin)

admin.site.register(
    Categoria,
    DraggableMPTTAdmin,
    list_display=(
        'tree_actions',
        'indented_title',
        # ...more fields if you feel like it...
    ),
    list_display_links=(
        'indented_title',
    ),
)

class ContenidoBlogInline(admin.StackedInline):
    model = ContenidoBlog
    extra = 1


class ImagenPostInline(admin.TabularInline):
    model = ImagenPost
    extra = 1



class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = '__all__'
        widgets = {
            'titulo': forms.Textarea(attrs={'rows': 2, 'cols': 40, 'class': 'vLargeTextField'}),
            'slug': forms.TextInput(attrs={'class': 'vLargeTextField'}),
            'meta_title': forms.Textarea(attrs={'rows': 2, 'cols': 40, 'class': 'vLargeTextField'}),
            'meta_keywords': forms.Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'vLargeTextField'}),
            'meta_description': forms.Textarea(attrs={'rows': 4, 'cols': 40, 'class': 'vLargeTextField'}),
        }

class PostAdmin(admin.ModelAdmin):
    form = PostForm
    inlines = [ImagenPostInline, ContenidoBlogInline]
    list_filter = ('categorias', )
    # search_fields = ('titulo', 'slug', 'categorias__nombre', 'contenidoblog__contenido')
    search_fields = ('titulo', 'slug', 'categorias__nombre')

    # list_display = ('titulo', 'categoria', 'fecha', 'publicado', 'autor')
    # date_hierarchy = 'fecha'
    # ordering = ('publicado', 'fecha')
    # filter_horizontal = ('etiquetas',)
    # raw_id_fields = ('autor',)
    prepopulated_fields = {'slug': ('titulo',)}
    # readonly_fields = ('vistas',)



admin.site.register(Post, PostAdmin)
admin.site.register(ImagenPost)
admin.site.register(Etiqueta)