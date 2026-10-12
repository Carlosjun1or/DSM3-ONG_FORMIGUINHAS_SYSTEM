from django.urls import path

from . import views

urlpatterns = [
    path('', views.doacoes_view, name='doacoes'),
    path('cadastrar/', views.cadastro_doacao_view, name='cadastro_doacao'),
    path('<int:doacao_id>/', views.doacao_detalhe_view, name='doacao_detalhe'),
    path('<int:doacao_id>/editar/', views.editar_doacao_view, name='editar_doacao'),
    path('<int:doacao_id>/status/', views.atualizar_status_doacao_view, name='atualizar_status_doacao'),
    path('doadores/', views.doadores_view, name='doadores'),
    path('doadores/cadastrar/', views.cadastro_doador_view, name='cadastro_doador'),
    path('doadores/<int:doador_id>/', views.doador_detalhe_view, name='doador_detalhe'),
    path('doadores/<int:doador_id>/status/', views.atualizar_status_doador_view, name='atualizar_status_doador'),
    path('doadores/<int:doador_id>/editar/', views.editar_doador_view, name='editar_doador'),
]
