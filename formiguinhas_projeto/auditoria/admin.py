from django.contrib import admin

from .models import EventoAuditoria


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('data_evento', 'entidade', 'acao', 'usuario_nome', 'resumo')
    list_filter = ('entidade', 'acao')
    search_fields = ('resumo', 'usuario_nome')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
