from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('multiroes/', views.multiroes, name='multiroes'),
    path('praias-atuacao/', views.praias_atuacao, name='praias_atuacao'),
    path('calendario/', views.calendario, name='calendario'),
]