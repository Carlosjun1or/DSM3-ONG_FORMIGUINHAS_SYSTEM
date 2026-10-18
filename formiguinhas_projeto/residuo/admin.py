from django.contrib import admin

from auditoria.admin_utils import AuditedModelAdmin
from .models import DestinacaoResiduo, ResiduoColetado


@admin.register(ResiduoColetado)
class ResiduoColetadoAdmin(AuditedModelAdmin):
    list_display = ('id_residuo', 'acao', 'tipo', 'categoria', 'quantidade', 'unidade', 'registrado_por_nome', 'dt_registro')
    list_filter = ('tipo', 'categoria', 'unidade')
    search_fields = ('acao__local', 'registrado_por_nome', 'observacao')


@admin.register(DestinacaoResiduo)
class DestinacaoResiduoAdmin(AuditedModelAdmin):
    list_display = ('id_destinacao', 'residuo', 'tipo', 'quantidade', 'unidade', 'registrado_por_nome', 'dt_registro')
    list_filter = ('tipo', 'unidade')
    search_fields = ('residuo__acao__local', 'registrado_por_nome', 'observacao')
