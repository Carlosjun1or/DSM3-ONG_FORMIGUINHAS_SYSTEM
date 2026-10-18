from django.contrib import admin
from .models import Voluntario, Usuario
from auditoria.admin_utils import AuditedModelAdmin

admin.site.register((Voluntario, Usuario), AuditedModelAdmin)
