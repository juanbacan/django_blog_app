from django.contrib import admin
from django import forms
from django.contrib import messages
from django.utils.html import format_html
from mptt.admin import MPTTModelAdmin, DraggableMPTTAdmin
from .models import Post, ContenidoBlog, Categoria, ImagenPost, Etiqueta

# Importar funciones de publicación
from blog.facebook_blog import publicar_blog_facebook, republicar_blog_facebook, publicar_blog_con_link
from blog.telegram_blog import publicar_blog_telegram, republicar_blog_telegram
from blog.whatsapp_blog import publicar_blog_whatsapp_simple

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
    list_display = ('titulo', 'fecha', 'activo', 'facebook_status', 'telegram_status', 'whatsapp_status')
    list_filter = ('categorias', 'activo', 'publicado_facebook', 'publicado_telegram', 'publicado_whatsapp', 'fecha')
    search_fields = ('titulo', 'slug', 'categorias__nombre')
    prepopulated_fields = {'slug': ('titulo',)}
    
    # Campos de solo lectura - gestionados automáticamente por las acciones
    readonly_fields = (
        'publicado_facebook', 'url_post_facebook',
        'publicado_telegram', 'telegram_message_id', 'telegram_chat_id', 'url_post_telegram',
        'publicado_whatsapp', 'whatsapp_message_id', 'whatsapp_channel',
    )
    
    # Organizar campos en secciones
    fieldsets = (
        ('Información General', {
            'fields': ('titulo', 'slug', 'categorias', 'activo', 'fecha')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_keywords', 'meta_description'),
        }),
        ('Estado de Publicación en Redes Sociales', {
            'fields': (
                ('publicado_facebook', 'url_post_facebook'),
                ('publicado_telegram', 'url_post_telegram'),
                ('telegram_message_id', 'telegram_chat_id'),
                ('publicado_whatsapp', 'whatsapp_message_id', 'whatsapp_channel'),
            ),
            'classes': ('collapse',),
            'description': 'Estos campos se actualizan automáticamente al usar las acciones de publicación.'
        }),
    )
    
    actions = [
        'activate', 
        'desactivate', 
        'publicar_facebook', 
        'republicar_facebook',
        'publicar_telegram',
        'republicar_telegram',
        'publicar_whatsapp',
        'republicar_whatsapp',
        'publicar_todas_redes'
    ]

    @admin.display(description='Facebook')
    def facebook_status(self, obj):
        """Mostrar estado de publicación en Facebook"""
        if obj.publicado_facebook and obj.url_post_facebook:
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: bold;">✅ Publicado</a>',
                obj.url_post_facebook
            )
        elif obj.publicado_facebook:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⚠️ Publicado sin URL</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ No publicado</span>'
            )

    @admin.display(description='Telegram')
    def telegram_status(self, obj):
        """Mostrar estado de publicación en Telegram"""
        if obj.publicado_telegram and obj.url_post_telegram:
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: bold;">✅ Publicado</a>',
                obj.url_post_telegram
            )
        elif obj.publicado_telegram:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⚠️ Publicado sin URL</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ No publicado</span>'
            )

    @admin.display(description='WhatsApp')
    def whatsapp_status(self, obj):
        """Mostrar estado de publicación en WhatsApp"""
        if obj.publicado_whatsapp and obj.whatsapp_message_id:
            return format_html(
                '<span style="color: green; font-weight: bold;">✅ Publicado</span>'
            )
        elif obj.publicado_whatsapp:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⚠️ Publicado sin ID</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">❌ No publicado</span>'
            )

    def activate(self, request, queryset):
        """Activar posts seleccionados"""
        count = queryset.update(activo=True)
        messages.success(request, f"{count} post(s) activado(s)")
    
    activate.short_description = '✅ Activar Post'

    def desactivate(self, request, queryset):
        """Desactivar posts seleccionados"""
        count = queryset.update(activo=False)
        messages.success(request, f"{count} post(s) desactivado(s)")
    
    desactivate.short_description = '❌ Desactivar Post'

    def publicar_facebook(self, request, queryset):
        """Publicar posts seleccionados en Facebook"""
        publicados = 0
        errores = 0
        
        for post in queryset:
            if post.publicado_facebook:
                messages.warning(
                    request, 
                    f"El post '{post.titulo}' ya fue publicado en Facebook"
                )
                continue
                
            try:
                success, response, comment_success, comment_response = publicar_blog_con_link(post)
                
                if success:
                    publicados += 1
                    messages.success(
                        request,
                        f"✅ Post '{post.titulo}' publicado exitosamente en Facebook"
                    )
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"❌ Error publicando '{post.titulo}': {response.get('error', 'Error desconocido')}"
                    )
                    
            except Exception as e:
                errores += 1
                messages.error(
                    request,
                    f"💥 Error inesperado con '{post.titulo}': {str(e)}"
                )
        
        if publicados > 0:
            messages.success(request, f"🎉 {publicados} post(s) publicado(s) exitosamente")
        if errores > 0:
            messages.error(request, f"⚠️ {errores} post(s) con errores")

    publicar_facebook.short_description = '📘 Publicar en Facebook'

    def republicar_facebook(self, request, queryset):
        """Republicar posts seleccionados en Facebook (forzar)"""
        publicados = 0
        errores = 0
        
        for post in queryset:
            try:
                success, response, comment_success, comment_response = republicar_blog_facebook(post, forzar=True)
                
                if success:
                    publicados += 1
                    messages.success(
                        request,
                        f"✅ Post '{post.titulo}' republicado exitosamente en Facebook"
                    )
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"❌ Error republicando '{post.titulo}': {response.get('error', 'Error desconocido')}"
                    )
                    
            except Exception as e:
                errores += 1
                messages.error(
                    request,
                    f"💥 Error inesperado con '{post.titulo}': {str(e)}"
                )
        
        if publicados > 0:
            messages.success(request, f"🔄 {publicados} post(s) republicado(s) exitosamente")
        if errores > 0:
            messages.error(request, f"⚠️ {errores} post(s) con errores")

    republicar_facebook.short_description = '🔄 Republicar en Facebook'

    def publicar_telegram(self, request, queryset):
        """Publicar posts seleccionados en Telegram"""
        publicados = 0
        errores = 0
        
        for post in queryset:
            if post.publicado_telegram:
                messages.warning(
                    request, 
                    f"El post '{post.titulo}' ya fue publicado en Telegram"
                )
                continue
                
            try:
                success, response = publicar_blog_telegram(post)
                
                if success:
                    publicados += 1
                    messages.success(
                        request,
                        f"✅ Post '{post.titulo}' publicado exitosamente en Telegram"
                    )
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"❌ Error publicando '{post.titulo}': {response.get('error', 'Error desconocido')}"
                    )
                    
            except Exception as e:
                errores += 1
                messages.error(
                    request,
                    f"💥 Error inesperado con '{post.titulo}': {str(e)}"
                )
        
        if publicados > 0:
            messages.success(request, f"🎉 {publicados} post(s) publicado(s) en Telegram exitosamente")
        if errores > 0:
            messages.error(request, f"⚠️ {errores} post(s) con errores")

    publicar_telegram.short_description = '📱 Publicar en Telegram'

    def republicar_telegram(self, request, queryset):
        """Republicar posts seleccionados en Telegram (forzar)"""
        publicados = 0
        errores = 0
        
        for post in queryset:
            try:
                success, response = republicar_blog_telegram(post, forzar=True)
                
                if success:
                    publicados += 1
                    messages.success(
                        request,
                        f"✅ Post '{post.titulo}' republicado exitosamente en Telegram"
                    )
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"❌ Error republicando '{post.titulo}': {response.get('error', 'Error desconocido')}"
                    )
                    
            except Exception as e:
                errores += 1
                messages.error(
                    request,
                    f"💥 Error inesperado con '{post.titulo}': {str(e)}"
                )
        
        if publicados > 0:
            messages.success(request, f"🔄 {publicados} post(s) republicado(s) en Telegram exitosamente")
        if errores > 0:
            messages.error(request, f"⚠️ {errores} post(s) con errores")

    republicar_telegram.short_description = '🔄 Republicar en Telegram'

    def publicar_whatsapp(self, request, queryset):
        """Publicar posts seleccionados en WhatsApp"""
        publicados = 0
        errores = 0
        
        for post in queryset:
            if post.publicado_whatsapp:
                messages.warning(
                    request, 
                    f"El post '{post.titulo}' ya fue publicado en WhatsApp"
                )
                continue
                
            try:
                success, response = publicar_blog_whatsapp_simple(post)
                
                if success:
                    publicados += 1
                    messages.success(
                        request,
                        f"✅ Post '{post.titulo}' publicado exitosamente en WhatsApp"
                    )
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"❌ Error publicando '{post.titulo}': {response.get('error', 'Error desconocido')}"
                    )
                    
            except Exception as e:
                errores += 1
                messages.error(
                    request,
                    f"💥 Error inesperado con '{post.titulo}': {str(e)}"
                )
        
        if publicados > 0:
            messages.success(request, f"🎉 {publicados} post(s) publicado(s) en WhatsApp exitosamente")
        if errores > 0:
            messages.error(request, f"⚠️ {errores} post(s) con errores")

    publicar_whatsapp.short_description = '💬 Publicar en WhatsApp'

    def republicar_whatsapp(self, request, queryset):
        """Republicar posts seleccionados en WhatsApp (forzar)"""
        publicados = 0
        errores = 0
        
        for post in queryset:
            try:
                # Resetear estado antes de republicar
                if hasattr(post, 'publicado_whatsapp'):
                    post.publicado_whatsapp = False
                    post.whatsapp_message_id = None
                    post.whatsapp_channel = None
                    post.save(update_fields=['publicado_whatsapp', 'whatsapp_message_id', 'whatsapp_channel'])
                
                success, response = publicar_blog_whatsapp_simple(post)
                
                if success:
                    publicados += 1
                    messages.success(
                        request,
                        f"✅ Post '{post.titulo}' republicado exitosamente en WhatsApp"
                    )
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"❌ Error republicando '{post.titulo}': {response.get('error', 'Error desconocido')}"
                    )
                    
            except Exception as e:
                errores += 1
                messages.error(
                    request,
                    f"💥 Error inesperado con '{post.titulo}': {str(e)}"
                )
        
        if publicados > 0:
            messages.success(request, f"🔄 {publicados} post(s) republicado(s) en WhatsApp exitosamente")
        if errores > 0:
            messages.error(request, f"⚠️ {errores} post(s) con errores")

    republicar_whatsapp.short_description = '🔄 Republicar en WhatsApp'

    def publicar_todas_redes(self, request, queryset):
        """Publicar posts seleccionados en todas las redes sociales (Facebook, Telegram y WhatsApp)"""
        publicados_total = 0
        errores_total = 0
        
        for post in queryset:
            publicados_post = 0
            errores_post = 0
            
            # 1. PUBLICAR EN FACEBOOK
            if not post.publicado_facebook:
                try:
                    success_fb, response_fb, _, _ = publicar_blog_con_link(post)
                    if success_fb:
                        publicados_post += 1
                        messages.success(request, f"✅ Facebook - '{post.titulo}' publicado")
                    else:
                        errores_post += 1
                        messages.error(request, f"❌ Facebook - '{post.titulo}': {response_fb.get('error', 'Error desconocido')}")
                except Exception as e:
                    errores_post += 1
                    messages.error(request, f"💥 Facebook - '{post.titulo}': {str(e)}")
            else:
                messages.info(request, f"ℹ️ Facebook - '{post.titulo}' ya estaba publicado")
            
            # 2. PUBLICAR EN TELEGRAM
            if not post.publicado_telegram:
                try:
                    success_tg, response_tg = publicar_blog_telegram(post)
                    
                    if success_tg:
                        publicados_post += 1
                        messages.success(request, f"✅ Telegram - '{post.titulo}' publicado")
                    else:
                        errores_post += 1
                        messages.error(request, f"❌ Telegram - '{post.titulo}': {response_tg.get('error', 'Error desconocido')}")
                            
                except Exception as e:
                    errores_post += 1
                    messages.error(request, f"💥 Telegram - '{post.titulo}': {str(e)}")
            else:
                messages.info(request, f"ℹ️ Telegram - '{post.titulo}' ya estaba publicado")
            
            # 3. PUBLICAR EN WHATSAPP
            if not post.publicado_whatsapp:
                try:
                    success_wa, response_wa = publicar_blog_whatsapp_simple(post)
                        
                    if success_wa:
                        publicados_post += 1
                        messages.success(request, f"✅ WhatsApp - '{post.titulo}' publicado")
                    else:
                        errores_post += 1
                        messages.error(request, f"❌ WhatsApp - '{post.titulo}': {response_wa.get('error', 'Error desconocido')}")
                        
                except Exception as e:
                    errores_post += 1
                    messages.error(request, f"💥 WhatsApp - '{post.titulo}': {str(e)}")
            else:
                messages.info(request, f"ℹ️ WhatsApp - '{post.titulo}' ya estaba publicado")
            
            publicados_total += publicados_post
            errores_total += errores_post
        
        # Mensaje final resumido
        if publicados_total > 0:
            messages.success(request, f"🎉 RESUMEN: {publicados_total} publicaciones exitosas en total")
        if errores_total > 0:
            messages.error(request, f"⚠️ RESUMEN: {errores_total} errores en total")
        
        if publicados_total == 0 and errores_total == 0:
            messages.info(request, f"ℹ️ Todos los posts seleccionados ya estaban publicados en todas las redes")

    publicar_todas_redes.short_description = '🚀 Publicar en TODAS las redes sociales'



admin.site.register(Post, PostAdmin)
admin.site.register(ImagenPost)
admin.site.register(Etiqueta)