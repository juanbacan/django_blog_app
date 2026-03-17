from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.module_loading import import_string


class InheritableContextMixin:
    extra_context = None

    def get_extra_context(self, request=None, **kwargs):
        """Hook para que subclases agreguen o sobreescriban contexto."""
        return {}

    def get_merged_context(self, request=None, **kwargs):
        context = dict(kwargs)

        if self.extra_context:
            context.update(self.extra_context)

        hook_context = getattr(self, 'hook_context', None)
        if hook_context:
            context.update(hook_context)

        dynamic_context = self.get_extra_context(request=request, **context)
        if dynamic_context:
            context.update(dynamic_context)

        return context

    def render_with_context(self, request, template_name, **context):
        return render(request, template_name, self.get_merged_context(request=request, **context))


class HookAccessMixin:
    """
    Mixin para permitir hooks de acceso personalizables por modo de juego.
    Permite que el usuario final configure la logica de acceso mediante settings.
    """
    access_hook_key = None

    def dispatch(self, request, *args, **kwargs):
        # Ejemplo: BLOG_ACCESS_HOOKS = {
        #   'simulador_avanzado': 'path.to.hook_avanzado',
        #   'simulador_basico_categoria': 'path.to.hook_basico',
        #   'pregunta_detalle': 'path.to.hook_pregunta',
        # }
        hooks_config = getattr(settings, 'BLOG_ACCESS_HOOKS', {})
        if not isinstance(hooks_config, dict):
            hooks_config = {}

        hook_path = hooks_config.get(self.access_hook_key)
        self.hook_context = {}

        if hook_path:
            try:
                hook_func = import_string(hook_path)
                result = hook_func(request, **kwargs)

                if isinstance(result, HttpResponse):
                    return result

                if isinstance(result, dict):
                    self.hook_context = result
            except (ImportError, AttributeError):
                pass

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(getattr(self, 'hook_context', {}))
        return context