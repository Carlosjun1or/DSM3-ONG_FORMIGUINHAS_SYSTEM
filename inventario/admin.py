from django.contrib import admin
from .models import Material, Movimentacao


#  AdminSite customizado
class CustomAdminSite(admin.AdminSite):
    site_header = "ONG Formiguinhas - Controle de Estoque"
    site_title = "Formiguinhas Admin"
    index_title = "Bem-vindo ao Sistema de Inventário"


# Instância do nosso Admin customizado
custom_admin_site = CustomAdminSite(name="custom_admin")


#  Materiais
@admin.register(Material, site=custom_admin_site)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'quantidade_inicial', 'saldo', 'unidade')
    search_fields = ('nome', 'codigo')

    class Media:
        css = {
            'all': ('inventario/css/style.css',)  # caminho relativo dentro de static/
        }

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Consulta de Estoque - ONG Formiguinhas"
        return super().changelist_view(request, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Cadastrar Material - ONG Formiguinhas"
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Editar Material - ONG Formiguinhas"
        return super().change_view(request, object_id, form_url, extra_context=extra_context)


#  Movimentações
@admin.register(Movimentacao, site=custom_admin_site)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('material', 'tipo', 'quantidade', 'usuario', 'data')
    list_filter = ('tipo', 'data')
    exclude = ('usuario',)
class Media:
    css = {
            'all': ('inventario/css/style.css',)
    }
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "material":
            kwargs["empty_label"] = "Selecione um material"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Histórico de Movimentações - ONG Formiguinhas"
        return super().changelist_view(request, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Registrar Movimentação - ONG Formiguinhas"
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Editar Movimentação - ONG Formiguinhas"
        return super().change_view(request, object_id, form_url, extra_context=extra_context)
