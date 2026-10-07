from django.urls import path
from django.views.generic import TemplateView

from blog import views
from blog.feeds import LatestPostsFeed

app_name = 'blog'

urlpatterns = [
    path('', views.index, name='index'),
    path('post/<slug:slug>/', views.post_detail, name='post'),
    path('post/<slug:slug>/curtir/', views.like_toggle, name='like_toggle'),
    path('post/<slug:slug>/comentar/', views.comment_create, name='comment_create'),
    path('comentario/<int:pk>/apagar/', views.comment_delete, name='comment_delete'),
    path('categoria/<slug:slug>/', views.category, name='category'),
    path('feed/', LatestPostsFeed(), name='feed'),
    path('privacidade/', TemplateView.as_view(template_name='blog/pages/privacy.html'),
         name='privacy'),
]
