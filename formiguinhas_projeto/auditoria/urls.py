from django.urls import path
from .views import global_auditoria

urlpatterns = [path('', global_auditoria, name='auditoria_global')]
