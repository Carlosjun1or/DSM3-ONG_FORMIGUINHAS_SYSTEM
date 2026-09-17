from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('', include('site_institucional.urls')),
]