from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('usuario/', include('usuario.urls')),
    path('estoque/', include('estoque.urls')),
    path('', RedirectView.as_view(pattern_name='materiais', permanent=False)),
]
