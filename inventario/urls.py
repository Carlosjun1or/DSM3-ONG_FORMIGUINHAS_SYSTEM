from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("consulta/", views.consulta_estoque, name="consulta_estoque"),
    path("cadastro-material/", views.cadastro_material, name="cadastro_material"),
    path("movimentacao/", views.movimentacao, name="movimentacao"),
    path("movimentacoes/", views.movimentacoes, name="movimentacoes"),
    path("usuarios/", views.usuarios, name="usuarios"),
    path("", views.dashboard, name="dashboard"),
    path("relatorio/", views.relatorio_estoque, name="relatorio_estoque"),
    path("materiais/", views.consulta_estoque, name="consulta_estoque"),

]

