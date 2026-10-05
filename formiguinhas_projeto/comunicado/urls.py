from django.urls import path
from . import views

urlpatterns = [
    path('admin/', views.admin_lista, name='comunicados_admin'),
    path('admin/cadastrar/', views.admin_form, name='comunicado_cadastrar'),
    path('admin/<int:comunicado_id>/editar/', views.admin_form, name='comunicado_editar'),
    path('admin/<int:comunicado_id>/<str:acao>/', views.admin_status, name='comunicado_status'),
    path('admin/relacionamentos/', views.relacionamentos, name='comunicado_relacionamentos'),
    path('admin/temas/', views.temas, name='temas_comunicados'),
    path('admin/temas/cadastrar/', views.tema_form, name='tema_cadastrar'),
    path('admin/temas/<int:tema_id>/editar/', views.tema_form, name='tema_editar'),
    path('central/', views.internos, name='central_comunicados'),
    path('central/<int:comunicado_id>/', views.interno_detalhe, name='comunicado_interno_detalhe'),
    path('publicos/', views.publicos, name='comunicados_publicos'),
    path('publicos/<int:comunicado_id>/', views.publico_detalhe, name='comunicado_publico_detalhe'),
]
