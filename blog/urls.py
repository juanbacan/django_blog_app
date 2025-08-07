from django.urls import path
from django.conf import settings
from .views import *


app_name = 'blog'

base_path_post = getattr(settings, 'BLOG_PATH_POST', 'post')
base_path_list_posts = getattr(settings, 'BLOG_PATH_LIST_POSTS', 'posts')
base_path_category = getattr(settings, 'BLOG_PATH_CATEGORY', 'categoria')

urlpatterns = [
    path(f'{base_path_post}/<str:slug>/', PostView.as_view(), name='post'),
    path(f'{base_path_category}/<slug:categoria>/', PostsCategoriaListView.as_view(), name='posts_categoria'),
    path(f'{base_path_list_posts}/', PostsListView.as_view(), name='posts'),
]