from django.urls import path

from . import views


urlpatterns = [
    path('', views.equipes_view, name='equipes'),
    path('cadastrar/', views.cadastro_equipe_view, name='cadastro_equipe'),
    path('<int:equipe_id>/', views.equipe_detalhe_view, name='equipe_detalhe'),
    path('<int:equipe_id>/editar/', views.editar_equipe_view, name='editar_equipe'),
    path('<int:equipe_id>/status/', views.atualizar_status_equipe_view, name='atualizar_status_equipe'),
    path('<int:equipe_id>/excluir/', views.excluir_equipe_view, name='excluir_equipe'),
    path('<int:equipe_id>/membros/adicionar/', views.adicionar_membro_view, name='adicionar_membro_equipe'),
    path('<int:equipe_id>/membros/<int:membro_id>/funcao/', views.atualizar_funcao_membro_view, name='atualizar_funcao_membro'),
    path('<int:equipe_id>/membros/<int:membro_id>/remover/', views.remover_membro_view, name='remover_membro_equipe'),
    path('<int:equipe_id>/membros/<int:membro_id>/historico/excluir/', views.excluir_historico_membro_view, name='excluir_historico_membro'),
]
