from django.contrib import admin
from auditoria.admin_utils import AuditedModelAdmin
from .models import Comunicado, ComunicadoAcao, ComunicadoEquipe, ComunicadoPraia, Tema

admin.site.register(
    (Comunicado, Tema, ComunicadoPraia, ComunicadoEquipe, ComunicadoAcao),
    AuditedModelAdmin,
)
