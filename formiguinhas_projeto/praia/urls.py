from django.urls import path

from . import views


urlpatterns = [
    path('', views.praias_view, name='praias_inicio'),
    path('praias/', views.praias_view, name='praias'),
    path('praias/cadastrar/', views.cadastrar_praia_view, name='cadastrar_praia'),
    path('praias/<int:praia_id>/editar/', views.editar_praia_view, name='editar_praia'),
    path('praias/<int:praia_id>/status/', views.atualizar_status_praia_view, name='atualizar_status_praia'),
    path('praias/<int:praia_id>/excluir/', views.excluir_praia_view, name='excluir_praia'),
]
