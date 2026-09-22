from django.urls import path
from . import views

urlpatterns = [
    path('consulta/', views.consulta_estoque, name='consulta_estoque'),
    path('historico/', views.historico_movimentacoes, name='historico'),
    path('cadastro-material/', views.cadastro_material, name='cadastro_material'),
    path('movimentacao/', views.movimentacao, name='movimentacao'),
    path('usuarios/', views.usuarios, name='usuarios'),
]
