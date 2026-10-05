from django.contrib import admin
from .models import Comunicado, ComunicadoAcao, ComunicadoEquipe, ComunicadoPraia, Tema

admin.site.register((Comunicado, Tema, ComunicadoPraia, ComunicadoEquipe, ComunicadoAcao))
