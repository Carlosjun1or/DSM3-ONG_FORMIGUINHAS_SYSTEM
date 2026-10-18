from django.contrib import admin

from auditoria.admin_utils import AuditedModelAdmin
from .models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial


@admin.register(Doacao)
class DoacaoAdmin(AuditedModelAdmin):
    readonly_fields = ('tipo', 'status')


@admin.register(ItemDoacaoMaterial)
class ItemDoacaoMaterialAdmin(AuditedModelAdmin):
    readonly_fields = tuple(field.name for field in ItemDoacaoMaterial._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register([Doador, DoacaoFinanceira], AuditedModelAdmin)
