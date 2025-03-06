from django.shortcuts import render
from django.views.generic import ListView, View
from django.db.models import Q
from .models import Post, Categoria

from core.utils import get_url_params


# class PostsView(View):
#     def get(self, request, *args, **kwargs):
#         context = {}
#         context['ultimas_noticias'] = Post.objects.ultimas_noticias()

#         context['nacionales'] = Post.objects.nacionales()
#         context['locales'] = Post.objects.locales()
#         context['internacionales'] = Post.objects.internacionales()
#         context['deportes'] = Post.objects.deportes()
        
#         return render(request, 'blog/posts.html', context)


class PostView(View):
    template_name = 'blog/post.html'


    def get(self, request, *args, **kwargs):
        context = {}
        slug = kwargs['slug']
        post = Post.objects.get(slug=slug)
        context['post'] = Post.objects.get(slug=slug)
        context['posts'] = Post.objects.exclude(slug=slug).order_by('-fecha')[:6]
        return render(request, 'blog/post.html', context)


class PostsListView(ListView):
    model = Post
    template_name = 'blog/posts.html'
    context_object_name = 'posts'
    paginate_by = 20
    page_kwarg = 'pagina'

    def get_queryset(self):
        posts = Post.objects.all()

        kword = self.request.GET.get("kword", None)
        if kword:
            posts = posts.filter(
                Q(titulo__search=kword) | Q(titulo__unaccent__icontains=kword) |
                Q(contenidoblog__contenido__unaccent__icontains=kword) |
                Q(contenidoblog__contenido__search=kword)
            ).distinct()

        return posts.order_by('-fecha')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Lista de Filtros
        context['lista_categorias'] = Categoria.objects.all().order_by('nombre')

        context['url'] = self.request.get_full_path()
        context['url_params'] = get_url_params(self.request)
        context['kword'] = self.request.GET.get("kword", None)
        return context


class PostsCategoriaListView(ListView):
    model = Post
    template_name = 'blog/posts_categoria.html'
    context_object_name = 'posts'
    paginate_by = 20
    page_kwarg = 'pagina'

    def get_queryset(self):
        slug = self.kwargs['categoria']
        return Post.objects.filter(categorias__slug=slug)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs['categoria']
        context['categoria'] = categoria = Categoria.objects.get(slug=slug)
        context['categoria_filtro'] = categoria

        # Lista de Filtros
        context['lista_categorias'] = Categoria.objects.all().order_by('nombre')

        context['url'] = self.request.get_full_path()
        context['url_params'] = get_url_params(self.request)
        context['kword'] = self.request.GET.get("kword", None)
        return context

