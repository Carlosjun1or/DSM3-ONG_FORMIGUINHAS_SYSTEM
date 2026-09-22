from django.urls import path

from . import views


urlpatterns = [
    path('', views.condominios_view, name='condominios'),
    path('bags/', views.bags_view, name='bags'),
    path('auditoria/', views.auditorias_view, name='auditorias'),
    path('cadastrar/', views.cadastrar_condominio_view, name='cadastrar_condominio'),
    path('<int:condominio_id>/editar/', views.editar_condominio_view, name='editar_condominio'),
    path('<int:condominio_id>/', views.detalhe_condominio_view, name='detalhe_condominio'),
    path('bags/cadastrar/', views.cadastrar_bag_view, name='cadastrar_bag'),
    path('bags/<int:bag_id>/', views.detalhe_bag_view, name='detalhe_bag'),
    path('bags/<int:bag_id>/editar/', views.editar_bag_view, name='editar_bag'),
    path('bags/<int:bag_id>/movimentar/', views.cadastrar_movimentacao_view, name='cadastrar_movimentacao_bag'),
]
