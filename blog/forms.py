from django import forms
from tinymce.widgets import TinyMCE
        
from core.forms import BaseForm


class PostInfoForm(BaseForm):
    titulo = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Titulo del post',}))
    fecha = forms.DateTimeField(required=True, widget=forms.TextInput(attrs={'placeholder': 'Fecha del post', 'type': 'date'}))
    slug = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Slug del post'}))
    contenido = forms.CharField(widget=TinyMCE(attrs={'cols': 80, 'rows': 10}))


class PostMetaForm(BaseForm):
    meta_title = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Meta title del post', 'width': 6}))
    meta_keywords = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Meta keywords del post', 'width': 6}))
    meta_description = forms.CharField(max_length=100, required=True, widget=forms.Textarea(attrs={'placeholder': 'Meta description del post', 'rows': 5, 'cols': 80}))


class ImagePostForm(BaseForm):
    imagen = forms.ImageField(required=True, widget=forms.FileInput(attrs={'placeholder': 'Imagen del post'}))
