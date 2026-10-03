from django.urls import path

from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('', views.profile, name='profile'),
    path('foto/', views.avatar_update, name='avatar'),
    path('senha/', views.AccountPasswordChangeView.as_view(), name='password_change'),
    path('excluir/', views.delete_account, name='delete'),
    path('criar/', views.register, name='register'),
    path('entrar/', views.EmailLoginView.as_view(), name='login'),
    path('sair/', views.AccountLogoutView.as_view(), name='logout'),
    path('esqueci-senha/', views.AccountPasswordResetView.as_view(), name='password_reset'),
    path('esqueci-senha/enviado/', views.AccountPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('nova-senha/<uidb64>/<token>/', views.AccountPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('nova-senha/concluido/', views.AccountPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
