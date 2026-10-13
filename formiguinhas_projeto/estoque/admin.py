from django.contrib import admin

from .models import Material, MovimentacaoEstoque


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'categoria', 'unidade', 'donativo', 'estoque_minimo')
    list_filter = ('categoria', 'donativo')
    search_fields = ('nome', 'codigo')


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Registros de movimentação são trilha de auditoria: sem criar, editar ou excluir."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(SomenteLeituraAdmin):
    list_display = ('material', 'tipo', 'quantidade', 'origem', 'registrado_por_nome', 'dt_cadastro')
    list_filter = ('tipo', 'origem')
    search_fields = ('material__nome', 'material__codigo')
