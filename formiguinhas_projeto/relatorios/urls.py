from django.urls import path

from . import views


urlpatterns = [
    path('', views.relatorios_view, name='relatorios'),
]
