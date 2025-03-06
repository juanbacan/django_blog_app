from django.urls import path
from .views import *

app_name = 'blog'

urlpatterns = [
    path('post/<str:slug>/', PostView.as_view(), name='post'),
    path('categoria/<slug:categoria>/', PostsCategoriaListView.as_view(), name='posts_categoria'),
    path('posts/', PostsListView.as_view(), name='posts'),

]   