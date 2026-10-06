from django.urls import path

from . import views

urlpatterns = [
    path('', views.residuos_view, name='residuos'),
    path('bag/<int:bag_id>/cadastrar/', views.registrar_coleta_bag_view, name='registrar_coleta_bag'),
    path('coleta/<int:coleta_id>/', views.detalhe_coleta_residuo_view, name='detalhe_coleta_residuo'),
    path('coleta/<int:coleta_id>/item/adicionar/', views.adicionar_item_coleta_view, name='adicionar_item_coleta'),
    path(
        'acao/<int:acao_id>/registrar/',
        views.registrar_residuo_view,
        name='registrar_residuo',
    ),
    path(
        'acao/<int:acao_id>/residuo/<int:residuo_id>/editar/',
        views.editar_residuo_view,
        name='editar_residuo',
    ),
    path(
        'acao/<int:acao_id>/residuo/<int:residuo_id>/excluir/',
        views.excluir_residuo_view,
        name='excluir_residuo',
    ),
    path(
        'acao/<int:acao_id>/residuo/<int:residuo_id>/destinacao/',
        views.registrar_destinacao_view,
        name='registrar_destinacao',
    ),
    path(
        'acao/<int:acao_id>/residuo/<int:residuo_id>/destinacao/<int:destinacao_id>/editar/',
        views.editar_destinacao_view,
        name='editar_destinacao',
    ),
    path(
        'acao/<int:acao_id>/residuo/<int:residuo_id>/destinacao/<int:destinacao_id>/excluir/',
        views.excluir_destinacao_view,
        name='excluir_destinacao',
    ),
]
