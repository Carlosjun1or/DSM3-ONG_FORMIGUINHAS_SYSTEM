from django.urls import path

from . import views


urlpatterns = [
    path('', views.materiais_view, name='materiais'),
    path('materiais/cadastrar/', views.cadastrar_material_view, name='cadastrar_material'),
    path('materiais/<int:material_id>/editar/', views.editar_material_view, name='editar_material'),
    path('movimentacoes/', views.movimentacoes_estoque_view, name='movimentacoes_estoque'),
    path('movimentacoes/cadastrar/', views.cadastrar_movimentacao_estoque_view, name='cadastrar_movimentacao_estoque'),
    path('movimentacoes/exportar/', views.exportar_movimentacoes_estoque_view, name='exportar_movimentacoes_estoque'),
    path('doacoes/', views.doacoes_estoque_view, name='doacoes_estoque'),
    path('doacoes/cadastrar/', views.cadastrar_doacao_estoque_view, name='cadastrar_doacao_estoque'),
    path('relatorio/', views.relatorio_estoque_view, name='relatorio_estoque'),
]
