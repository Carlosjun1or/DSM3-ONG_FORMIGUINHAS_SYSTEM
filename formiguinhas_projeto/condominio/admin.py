from django.contrib import admin

from .models import AuditoriaControle, Bag, Condominio, MovimentacaoBag


@admin.register(Condominio)
class CondominioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'praia', 'porte', 'status', 'dt_cadastro')
    list_filter = ('status', 'porte', 'confiabilidade', 'praia')
    search_fields = ('nome', 'cidade', 'responsavel_nome')


@admin.register(Bag)
class BagAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'condominio', 'status', 'percentual_ocupacao', 'dt_cadastro')
    list_filter = ('status',)
    search_fields = ('codigo', 'condominio__nome')


@admin.register(MovimentacaoBag)
class MovimentacaoBagAdmin(admin.ModelAdmin):
    list_display = ('bag', 'tipo', 'status_anterior', 'status_novo', 'data_movimentacao', 'registrado_por')
    list_filter = ('tipo', 'status_novo')
    search_fields = ('bag__codigo', 'registrado_por_nome')
    readonly_fields = ('status_anterior', 'registrado_por', 'registrado_por_nome')


@admin.register(AuditoriaControle)
class AuditoriaControleAdmin(admin.ModelAdmin):
    list_display = ('entidade', 'id_registro', 'acao', 'usuario_nome', 'data_evento', 'resumo')
    list_filter = ('entidade', 'acao', 'data_evento')
    search_fields = ('usuario_nome', 'resumo')
    readonly_fields = (
        'entidade', 'id_registro', 'acao', 'usuario', 'usuario_nome',
        'data_evento', 'resumo', 'valores_anteriores', 'valores_novos',
    )
