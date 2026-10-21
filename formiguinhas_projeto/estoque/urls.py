from django.urls import path
from django.views.generic import RedirectView

from . import views


urlpatterns = [
    path('materiais/', views.materiais_view, name='materiais'),
    path('', views.materiais_view, name='materiais_root'),
    path('materiais/cadastrar/', views.cadastrar_material_view, name='cadastrar_material'),
    path('materiais/<int:material_id>/editar/', views.editar_material_view, name='editar_material'),
    path('movimentacoes/', views.movimentacoes_estoque_view, name='movimentacoes_estoque'),
    path('movimentacoes/cadastrar/', views.cadastrar_movimentacao_estoque_view, name='cadastrar_movimentacao_estoque'),
    path('movimentacoes/exportar/', views.exportar_movimentacoes_estoque_view, name='exportar_movimentacoes_estoque'),
    path('doacoes/', RedirectView.as_view(pattern_name='doacoes', permanent=False), name='doacoes_estoque'),
    path('doacoes/cadastrar/', RedirectView.as_view(pattern_name='cadastro_doacao', permanent=False), name='cadastrar_doacao_estoque'),
    path('relatorio/', views.relatorio_estoque_view, name='relatorio_estoque'),
]
