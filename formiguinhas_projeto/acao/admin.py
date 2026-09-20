from django.contrib import admin

from .models import (
    Acao,
    AcaoEquipe,
    AcaoImagem,
    AcaoParticipante,
    AcaoParticipanteHistorico,
    AcaoResponsavel,
)


@admin.register(Acao)
class AcaoAdmin(admin.ModelAdmin):
    list_display = ('id_acao', 'tipo', 'praia', 'data', 'status')
    list_filter = ('tipo', 'status', 'praia')
    search_fields = ('local', 'descricao')


@admin.register(AcaoImagem)
class AcaoImagemAdmin(admin.ModelAdmin):
    list_display = ('id_acao_imagem', 'acao', 'descricao', 'dt_cadastro')
    list_filter = ('acao__tipo',)
    search_fields = ('acao__local', 'descricao')


@admin.register(AcaoEquipe)
class AcaoEquipeAdmin(admin.ModelAdmin):
    list_display = ('id_acao_equipe', 'acao', 'equipe')
    list_filter = ('acao__tipo', 'equipe__praia')
    search_fields = ('acao__local', 'equipe__nome')


@admin.register(AcaoParticipante)
class AcaoParticipanteAdmin(admin.ModelAdmin):
    list_display = ('id_acao_participante', 'acao', 'voluntario', 'status', 'compareceu')
    list_filter = ('status', 'compareceu', 'acao__tipo')
    search_fields = ('voluntario__nome', 'acao__local')


@admin.register(AcaoParticipanteHistorico)
class AcaoParticipanteHistoricoAdmin(admin.ModelAdmin):
    list_display = (
        'id_historico',
        'acao',
        'voluntario',
        'status',
        'dt_movimentacao',
        'movido_por_nome',
    )
    list_filter = ('status', 'acao__tipo')
    search_fields = ('voluntario__nome', 'acao__local', 'movido_por_nome')


@admin.register(AcaoResponsavel)
class AcaoResponsavelAdmin(admin.ModelAdmin):
    list_display = ('id_acao_responsavel', 'acao', 'voluntario', 'papel')
    list_filter = ('papel', 'acao__tipo')
    search_fields = ('voluntario__nome', 'acao__local')
