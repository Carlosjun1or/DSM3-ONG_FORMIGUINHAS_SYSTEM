from django.contrib import admin

from auditoria.admin_utils import AuditedModelAdmin
from .models import Equipe, EquipeMembro


@admin.register(Equipe)
class EquipeAdmin(AuditedModelAdmin):
    list_display = ('nome', 'status', 'dt_cadastro')
    list_filter = ('status',)
    search_fields = ('nome', 'descricao')


@admin.register(EquipeMembro)
class EquipeMembroAdmin(AuditedModelAdmin):
    list_display = ('equipe', 'voluntario', 'papel', 'status', 'dt_entrada', 'dt_saida')
    list_filter = ('papel', 'status')
    search_fields = ('equipe__nome', 'voluntario__nome')
