from django.urls import path

from . import views

urlpatterns = [
    path('', views.acoes_view, name='acoes'),
    path('cadastrar/', views.cadastro_acao_view, name='cadastro_acao'),
    path('<int:acao_id>/', views.acao_detalhe_view, name='acao_detalhe'),
    path('<int:acao_id>/editar/', views.editar_acao_view, name='editar_acao'),
    path('<int:acao_id>/excluir/', views.excluir_acao_view, name='excluir_acao'),
    path('<int:acao_id>/status/', views.atualizar_status_acao_view, name='atualizar_status_acao'),
    path('<int:acao_id>/participantes/adicionar/', views.adicionar_participante_view, name='adicionar_participante_acao'),
    path('<int:acao_id>/responsaveis/adicionar/', views.adicionar_responsavel_view, name='adicionar_responsavel_acao'),
    path('<int:acao_id>/imagens/adicionar/', views.adicionar_imagens_acao_view, name='adicionar_imagens_acao'),
    path('<int:acao_id>/imagens/<int:imagem_id>/excluir/', views.excluir_imagem_acao_view, name='excluir_imagem_acao'),
    path('<int:acao_id>/participantes/<int:participante_id>/confirmar/', views.confirmar_participacao_view, name='confirmar_participacao_acao'),
    path('<int:acao_id>/participantes/<int:participante_id>/compareceu/', views.registrar_comparecimento_view, name='registrar_comparecimento_acao'),
    path('<int:acao_id>/historico/<int:historico_id>/restaurar/', views.restaurar_participante_view, name='restaurar_participante_acao'),
]
