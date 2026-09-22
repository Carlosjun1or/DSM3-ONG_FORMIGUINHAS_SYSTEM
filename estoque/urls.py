"""
URL configuration for estoque project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.contrib.auth import views as auth_views
from inventario.views import remover_usuario, dashboard, movimentacoes, usuarios, consulta_estoque
from inventario.admin import custom_admin_site   # importa o admin customizado

urlpatterns = [
    # Admin customizado
    path('admin/', custom_admin_site.urls),

    # Rotas do app inventario
    path('inventario/', include('inventario.urls')),

    # Se quiser manter também o prefixo "estoque"
    path('estoque/', include('inventario.urls')),

    # Login e logout
   path('login/', auth_views.LoginView.as_view(template_name='inventario/login.html'), name='login'),
   path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),


    # Remover usuário
    path('usuarios/remover/<int:usuario_id>/', remover_usuario, name='remover_usuario'),

    # Dashboard inicial
    path('', dashboard, name='dashboard'),

    # Rotas diretas para os atalhos do dashboard
    path('movimentacoes/', movimentacoes, name='movimentacoes'),
    path('usuarios/', usuarios, name='usuarios'),
    path('estoque/consulta/', consulta_estoque, name='consulta_estoque'),
]























