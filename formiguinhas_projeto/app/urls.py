from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('cadastro-voluntario/', views.cadastro_voluntario_view, name='cadastro_voluntario'),
    path('cadastro-usuario/', views.cadastro_usuario_view, name='cadastro_usuario'),
    path('home/', views.home_view, name='home'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('alterar-senha/', views.alterar_senha_view, name='alterar_senha'),
]