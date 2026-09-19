from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('cadastro-voluntario/', views.cadastro_voluntario_view, name='cadastro_voluntario'),
    path('cadastro-usuario/', views.cadastro_usuario_view, name='cadastro_usuario'),
    path('home/', views.home_view, name='home'),
    path('voluntarios/', views.voluntarios_view, name='voluntarios'),
    path('voluntarios/<int:voluntario_id>/editar/', views.editar_voluntario_view, name='editar_voluntario'),
    path('voluntarios/<int:voluntario_id>/status/', views.atualizar_status_voluntario_view, name='atualizar_status_voluntario'),
    path('voluntarios/<int:voluntario_id>/excluir/', views.excluir_voluntario_view, name='excluir_voluntario'),
    path('usuarios/', views.usuarios_view, name='usuarios'),
    path('usuarios/<int:usuario_id>/tipo/', views.atualizar_tipo_usuario_view, name='atualizar_tipo_usuario'),
    path('usuarios/<int:usuario_id>/editar/', views.editar_usuario_view, name='editar_usuario'),
    path('usuarios/<int:usuario_id>/excluir/', views.excluir_usuario_view, name='excluir_usuario'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('alterar-senha/', views.alterar_senha_view, name='alterar_senha'),
]