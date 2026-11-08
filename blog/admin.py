from django.contrib import admin
from django import forms
from django.contrib import messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.shortcuts import render
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from mptt.admin import DraggableMPTTAdmin

from .models import Post, ContenidoBlog, Categoria, ImagenPost, Etiqueta
from blog.facebook_blog import (
    publicar_post_facebook,
    hacer_publico_post_facebook,
)
from blog.telegram_blog import publicar_blog_telegram, republicar_blog_telegram
from blog.whatsapp_blog import publicar_blog_whatsapp_simple


admin.site.register(
    Categoria,
    DraggableMPTTAdmin,
    list_display=(
        'tree_actions',
        'indented_title',
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


class FacebookPublishForm(forms.Form):
    titulo = forms.CharField(
        required=False,
        label='Título / hook',
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 60}),
        help_text='Vacío = usar título del post.',
    )
    descripcion = forms.CharField(
        required=False,
        label='Descripción',
        widget=forms.Textarea(attrs={'rows': 4, 'cols': 60}),
        help_text='Vacío = usar meta_description del post.',
    )
    primer_comentario = forms.CharField(
        required=False,
        label='Primer comentario',
        widget=forms.Textarea(attrs={'rows': 3, 'cols': 60}),
        help_text='Solo se publica si el post queda público. Vacío = link al artículo.',
    )


class PostAdmin(admin.ModelAdmin):
    form = PostForm
    inlines = [ImagenPostInline, ContenidoBlogInline]
    list_display = (
        'titulo',
        'fecha',
        'activo',
        'destacado',
        'facebook_status',
        'telegram_status',
        'whatsapp_status',
    )
    list_filter = (
        'categorias',
        'activo',
        'destacado',
        'facebook_estado',
        'publicado_facebook',
        'publicado_telegram',
        'publicado_whatsapp',
        'fecha',
    )
    search_fields = ('titulo', 'slug', 'categorias__nombre')
    prepopulated_fields = {'slug': ('titulo',)}

    readonly_fields = (
        'publicado_facebook',
        'facebook_estado',
        'facebook_post_id',
        'url_post_facebook',
        'facebook_titulo_usado',
        'facebook_descripcion_usada',
        'facebook_comentario_usado',
        'publicado_telegram',
        'telegram_message_id',
        'telegram_chat_id',
        'url_post_telegram',
        'publicado_whatsapp',
        'whatsapp_message_id',
        'whatsapp_channel',
    )

    fieldsets = (
        ('Información General', {
            'fields': ('titulo', 'slug', 'categorias', 'activo', 'destacado', 'fecha'),
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_keywords', 'meta_description'),
        }),
        ('Estado de Publicación en Redes Sociales', {
            'fields': (
                ('facebook_estado', 'publicado_facebook'),
                ('facebook_post_id', 'url_post_facebook'),
                'facebook_titulo_usado',
                'facebook_descripcion_usada',
                'facebook_comentario_usado',
                ('publicado_telegram', 'url_post_telegram'),
                ('telegram_message_id', 'telegram_chat_id'),
                ('publicado_whatsapp', 'whatsapp_message_id', 'whatsapp_channel'),
            ),
            'classes': ('collapse',),
            'description': 'Campos actualizados por las acciones de publicación / MCP.',
        }),
    )

    actions = [
        'activate',
        'desactivate',
        'publicar_facebook_draft',
        'publicar_facebook_publico',
        'hacer_publico_facebook',
        'publicar_facebook_forzar',
        'publicar_telegram',
        'republicar_telegram',
        'publicar_whatsapp',
        'republicar_whatsapp',
        'publicar_todas_redes',
    ]

    @admin.display(description='Facebook')
    def facebook_status(self, obj):
        estado = getattr(obj, 'facebook_estado', None) or (
            'publico' if obj.publicado_facebook else 'no_publicado'
        )
        if estado == 'publico' and obj.url_post_facebook:
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: bold;">Publico</a>',
                obj.url_post_facebook,
            )
        if estado == 'draft':
            label = 'Draft'
            if obj.url_post_facebook:
                return format_html(
                    '<a href="{}" target="_blank" style="color: #b36b00; font-weight: bold;">{}</a>',
                    obj.url_post_facebook,
                    label,
                )
            return mark_safe(
                '<span style="color: #b36b00; font-weight: bold;">Draft</span>'
            )
        if estado == 'error':
            return mark_safe('<span style="color: red; font-weight: bold;">Error</span>')
        if obj.publicado_facebook:
            return mark_safe(
                '<span style="color: orange; font-weight: bold;">Publicado sin URL</span>'
            )
        return mark_safe('<span style="color: red; font-weight: bold;">No publicado</span>')

    @admin.display(description='Telegram')
    def telegram_status(self, obj):
        if obj.publicado_telegram and obj.url_post_telegram:
            return format_html(
                '<a href="{}" target="_blank" style="color: green; font-weight: bold;">Publicado</a>',
                obj.url_post_telegram,
            )
        if obj.publicado_telegram:
            return mark_safe(
                '<span style="color: orange; font-weight: bold;">Publicado sin URL</span>'
            )
        return mark_safe('<span style="color: red; font-weight: bold;">No publicado</span>')

    @admin.display(description='WhatsApp')
    def whatsapp_status(self, obj):
        if obj.publicado_whatsapp and obj.whatsapp_message_id:
            return mark_safe('<span style="color: green; font-weight: bold;">Publicado</span>')
        if obj.publicado_whatsapp:
            return mark_safe(
                '<span style="color: orange; font-weight: bold;">Publicado sin ID</span>'
            )
        return mark_safe('<span style="color: red; font-weight: bold;">No publicado</span>')

    def activate(self, request, queryset):
        count = queryset.update(activo=True)
        messages.success(request, f'{count} post(s) activado(s)')

    activate.short_description = 'Activar Post'

    def desactivate(self, request, queryset):
        count = queryset.update(activo=False)
        messages.success(request, f'{count} post(s) desactivado(s)')

    desactivate.short_description = 'Desactivar Post'

    def _facebook_publish_action(
        self,
        request,
        queryset,
        *,
        action_name: str,
        modo: str,
        forzar: bool = False,
        title: str,
        description: str,
        confirm_label: str,
    ):
        posts = list(queryset)
        if not posts:
            messages.warning(request, 'No hay posts seleccionados.')
            return None

        show_overrides = len(posts) == 1
        if 'apply' in request.POST:
            form = FacebookPublishForm(request.POST) if show_overrides else None
            if show_overrides and form and not form.is_valid():
                return render(
                    request,
                    'admin/blog/facebook_publish_intermediate.html',
                    {
                        'title': title,
                        'description': description,
                        'confirm_label': confirm_label,
                        'action_name': action_name,
                        'action_checkbox_name': ACTION_CHECKBOX_NAME,
                        'posts': posts,
                        'form': form,
                        'show_overrides': True,
                        'opts': self.model._meta,
                    },
                )

            overrides = form.cleaned_data if show_overrides and form else {}
            titulo = (overrides.get('titulo') or None) if show_overrides else None
            descripcion = (overrides.get('descripcion') or None) if show_overrides else None
            primer_comentario = (
                overrides.get('primer_comentario') if show_overrides else None
            )
            # Empty string from form means "use default" → pass None
            if titulo == '':
                titulo = None
            if descripcion == '':
                descripcion = None
            if primer_comentario == '':
                primer_comentario = None

            ok_count = 0
            err_count = 0
            for post in posts:
                result = publicar_post_facebook(
                    post,
                    titulo=titulo,
                    descripcion=descripcion,
                    primer_comentario=primer_comentario,
                    modo=modo,
                    forzar=forzar,
                )
                if result.get('success'):
                    ok_count += 1
                    messages.success(
                        request,
                        f"Facebook ({modo}) OK: '{post.titulo}'"
                        + (f" → {result.get('permalink')}" if result.get('permalink') else ''),
                    )
                else:
                    err_count += 1
                    messages.error(
                        request,
                        f"Facebook error '{post.titulo}': {result.get('error', 'desconocido')}",
                    )

            if ok_count:
                messages.success(request, f'{ok_count} post(s) procesado(s) en Facebook')
            if err_count:
                messages.error(request, f'{err_count} post(s) con error en Facebook')
            return None

        initial = {}
        if show_overrides:
            post = posts[0]
            initial = {
                'titulo': post.titulo or '',
                'descripcion': post.meta_description or '',
                'primer_comentario': f'🔗 Lee el artículo completo aquí: {post.mi_url_absoluta}',
            }
        form = FacebookPublishForm(initial=initial)

        return render(
            request,
            'admin/blog/facebook_publish_intermediate.html',
            {
                'title': title,
                'description': description,
                'confirm_label': confirm_label,
                'action_name': action_name,
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
                'posts': posts,
                'form': form,
                'show_overrides': show_overrides,
                'opts': self.model._meta,
            },
        )

    def publicar_facebook_draft(self, request, queryset):
        return self._facebook_publish_action(
            request,
            queryset,
            action_name='publicar_facebook_draft',
            modo='draft',
            title='Publicar en Facebook (borrador)',
            description=(
                'Crea un borrador en Meta Business Suite → Contenido → Borradores. '
                'El primer comentario se aplicará al hacerlo público.'
            ),
            confirm_label='Crear borrador en Facebook',
        )

    publicar_facebook_draft.short_description = 'Facebook: crear borrador (draft)'

    def publicar_facebook_publico(self, request, queryset):
        return self._facebook_publish_action(
            request,
            queryset,
            action_name='publicar_facebook_publico',
            modo='public',
            title='Publicar en Facebook (público)',
            description='Publica el post en vivo en la Page y agrega el primer comentario.',
            confirm_label='Publicar en Facebook ahora',
        )

    publicar_facebook_publico.short_description = 'Facebook: publicar público'

    def publicar_facebook_forzar(self, request, queryset):
        return self._facebook_publish_action(
            request,
            queryset,
            action_name='publicar_facebook_forzar',
            modo='public',
            forzar=True,
            title='Publicar de nuevo en Facebook (forzar)',
            description=(
                'Crea un post NUEVO en Facebook aunque ya exista uno asociado. '
                'El post anterior en Facebook no se elimina.'
            ),
            confirm_label='Forzar nuevo post público',
        )

    publicar_facebook_forzar.short_description = 'Facebook: publicar de nuevo (forzar)'

    def hacer_publico_facebook(self, request, queryset):
        ok_count = 0
        err_count = 0
        for post in queryset:
            result = hacer_publico_post_facebook(post)
            if result.get('success'):
                ok_count += 1
                messages.success(
                    request,
                    f"Facebook público: '{post.titulo}'"
                    + (f" → {result.get('permalink')}" if result.get('permalink') else ''),
                )
            else:
                err_count += 1
                messages.error(
                    request,
                    f"No se pudo hacer público '{post.titulo}': {result.get('error')}",
                )
        if ok_count:
            messages.success(request, f'{ok_count} draft(s) publicados')
        if err_count:
            messages.error(request, f'{err_count} error(es) al hacer público')

    hacer_publico_facebook.short_description = 'Facebook: hacer público (desde draft)'

    def publicar_telegram(self, request, queryset):
        publicados = 0
        errores = 0
        for post in queryset:
            if post.publicado_telegram:
                messages.warning(request, f"El post '{post.titulo}' ya fue publicado en Telegram")
                continue
            try:
                success, response = publicar_blog_telegram(post)
                if success:
                    publicados += 1
                    messages.success(request, f"Telegram OK: '{post.titulo}'")
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"Telegram error '{post.titulo}': {response.get('error', 'Error desconocido')}",
                    )
            except Exception as e:
                errores += 1
                messages.error(request, f"Telegram error '{post.titulo}': {e}")
        if publicados:
            messages.success(request, f'{publicados} post(s) en Telegram')
        if errores:
            messages.error(request, f'{errores} error(es) en Telegram')

    publicar_telegram.short_description = 'Publicar en Telegram'

    def republicar_telegram(self, request, queryset):
        publicados = 0
        errores = 0
        for post in queryset:
            try:
                success, response = republicar_blog_telegram(post, forzar=True)
                if success:
                    publicados += 1
                    messages.success(request, f"Telegram republicado: '{post.titulo}'")
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"Telegram error '{post.titulo}': {response.get('error', 'Error desconocido')}",
                    )
            except Exception as e:
                errores += 1
                messages.error(request, f"Telegram error '{post.titulo}': {e}")
        if publicados:
            messages.success(request, f'{publicados} post(s) republicados en Telegram')
        if errores:
            messages.error(request, f'{errores} error(es) en Telegram')

    republicar_telegram.short_description = 'Republicar en Telegram'

    def publicar_whatsapp(self, request, queryset):
        publicados = 0
        errores = 0
        for post in queryset:
            if post.publicado_whatsapp:
                messages.warning(request, f"El post '{post.titulo}' ya fue publicado en WhatsApp")
                continue
            try:
                success, response = publicar_blog_whatsapp_simple(post)
                if success:
                    publicados += 1
                    messages.success(request, f"WhatsApp OK: '{post.titulo}'")
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"WhatsApp error '{post.titulo}': {response.get('error', 'Error desconocido')}",
                    )
            except Exception as e:
                errores += 1
                messages.error(request, f"WhatsApp error '{post.titulo}': {e}")
        if publicados:
            messages.success(request, f'{publicados} post(s) en WhatsApp')
        if errores:
            messages.error(request, f'{errores} error(es) en WhatsApp')

    publicar_whatsapp.short_description = 'Publicar en WhatsApp'

    def republicar_whatsapp(self, request, queryset):
        publicados = 0
        errores = 0
        for post in queryset:
            try:
                if hasattr(post, 'publicado_whatsapp'):
                    post.publicado_whatsapp = False
                    post.whatsapp_message_id = None
                    post.whatsapp_channel = None
                    post.save(
                        update_fields=[
                            'publicado_whatsapp',
                            'whatsapp_message_id',
                            'whatsapp_channel',
                        ]
                    )
                success, response = publicar_blog_whatsapp_simple(post)
                if success:
                    publicados += 1
                    messages.success(request, f"WhatsApp republicado: '{post.titulo}'")
                else:
                    errores += 1
                    messages.error(
                        request,
                        f"WhatsApp error '{post.titulo}': {response.get('error', 'Error desconocido')}",
                    )
            except Exception as e:
                errores += 1
                messages.error(request, f"WhatsApp error '{post.titulo}': {e}")
        if publicados:
            messages.success(request, f'{publicados} post(s) republicados en WhatsApp')
        if errores:
            messages.error(request, f'{errores} error(es) en WhatsApp')

    republicar_whatsapp.short_description = 'Republicar en WhatsApp'

    def publicar_todas_redes(self, request, queryset):
        """Facebook en draft + Telegram + WhatsApp."""
        publicados_total = 0
        errores_total = 0

        for post in queryset:
            estado_fb = getattr(post, 'facebook_estado', None) or (
                'publico' if post.publicado_facebook else 'no_publicado'
            )
            if estado_fb in ('draft', 'publico'):
                messages.info(request, f"Facebook - '{post.titulo}' ya estaba en estado {estado_fb}")
            else:
                try:
                    result = publicar_post_facebook(post, modo='draft')
                    if result.get('success'):
                        publicados_total += 1
                        messages.success(request, f"Facebook draft - '{post.titulo}'")
                    else:
                        errores_total += 1
                        messages.error(
                            request,
                            f"Facebook - '{post.titulo}': {result.get('error', 'Error desconocido')}",
                        )
                except Exception as e:
                    errores_total += 1
                    messages.error(request, f"Facebook - '{post.titulo}': {e}")

            if not post.publicado_telegram:
                try:
                    success_tg, response_tg = publicar_blog_telegram(post)
                    if success_tg:
                        publicados_total += 1
                        messages.success(request, f"Telegram - '{post.titulo}' publicado")
                    else:
                        errores_total += 1
                        messages.error(
                            request,
                            f"Telegram - '{post.titulo}': {response_tg.get('error', 'Error desconocido')}",
                        )
                except Exception as e:
                    errores_total += 1
                    messages.error(request, f"Telegram - '{post.titulo}': {e}")
            else:
                messages.info(request, f"Telegram - '{post.titulo}' ya estaba publicado")

            if not post.publicado_whatsapp:
                try:
                    success_wa, response_wa = publicar_blog_whatsapp_simple(post)
                    if success_wa:
                        publicados_total += 1
                        messages.success(request, f"WhatsApp - '{post.titulo}' publicado")
                    else:
                        errores_total += 1
                        messages.error(
                            request,
                            f"WhatsApp - '{post.titulo}': {response_wa.get('error', 'Error desconocido')}",
                        )
                except Exception as e:
                    errores_total += 1
                    messages.error(request, f"WhatsApp - '{post.titulo}': {e}")
            else:
                messages.info(request, f"WhatsApp - '{post.titulo}' ya estaba publicado")

        if publicados_total:
            messages.success(request, f'RESUMEN: {publicados_total} publicaciones exitosas')
        if errores_total:
            messages.error(request, f'RESUMEN: {errores_total} errores')
        if publicados_total == 0 and errores_total == 0:
            messages.info(request, 'Todo ya estaba publicado / en draft')

    publicar_todas_redes.short_description = 'Publicar en TODAS las redes (FB draft)'


admin.site.register(Post, PostAdmin)
admin.site.register(ImagenPost)
admin.site.register(Etiqueta)
