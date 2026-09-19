from django.urls import path
from . import views

urlpatterns = [
    path('consulta/', views.consulta_estoque, name='consulta_estoque'),
    path('historico/', views.historico_movimentacoes, name='historico_movimentacoes'),
]
