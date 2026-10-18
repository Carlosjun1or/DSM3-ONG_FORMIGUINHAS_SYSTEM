from django.contrib import admin
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured

from usuario.models import Usuario

from .services import registrar_evento, snapshot


ENTIDADES_ADMIN = {
    ('usuario', 'usuario'): 'USUARIO',
    ('usuario', 'voluntario'): 'VOLUNTARIO',
    ('praia', 'praia'): 'PRAIA',
    ('equipe', 'equipe'): 'EQUIPE',
    ('equipe', 'equipemembro'): 'EQUIPE_MEMBRO',
    ('acao', 'acao'): 'ACAO',
    ('acao', 'acaoequipe'): 'ACAO_EQUIPE',
    ('acao', 'acaoimagem'): 'ACAO_IMAGEM',
    ('acao', 'acaoparticipante'): 'ACAO_PARTICIPANTE',
    ('acao', 'acaoparticipantehistorico'): 'ACAO_PARTICIPANTE_HISTORICO',
    ('acao', 'acaoresponsavel'): 'ACAO_RESPONSAVEL',
    ('residuo', 'coletaresiduo'): 'COLETA_RESIDUO',
    ('residuo', 'itemcoletaresiduo'): 'ITEM_COLETA_RESIDUO',
    ('residuo', 'residuocoletado'): 'RESIDUO',
    ('residuo', 'destinacaoresiduo'): 'DESTINACAO_RESIDUO',
    ('condominio', 'condominio'): 'CONDOMINIO',
    ('condominio', 'bag'): 'BAG',
    ('condominio', 'movimentacaobag'): 'MOVIMENTACAO',
    ('comunicado', 'comunicado'): 'COMUNICADO',
    ('comunicado', 'tema'): 'TEMA_COMUNICADO',
    ('comunicado', 'comunicadopraia'): 'COMUNICADO_PRAIA',
    ('comunicado', 'comunicadoequipe'): 'COMUNICADO_EQUIPE',
    ('comunicado', 'comunicadoacao'): 'COMUNICADO_ACAO',
    ('comunicado', 'comunicadodoacao'): 'COMUNICADO_DOACAO',
    ('doacao', 'doador'): 'DOADOR',
    ('doacao', 'doacao'): 'DOACAO',
    ('doacao', 'doacaofinanceira'): 'DOACAO_FINANCEIRA',
    ('doacao', 'itemdoacaomaterial'): 'ITEM_DOACAO_MATERIAL',
    ('estoque', 'material'): 'MATERIAL',
}


class AuditedModelAdmin(admin.ModelAdmin):
    def _audit_entity(self):
        key = (self.model._meta.app_label, self.model._meta.model_name)
        try:
            return ENTIDADES_ADMIN[key]
        except KeyError as error:
            raise ImproperlyConfigured(
                f'Nenhuma entidade de auditoria configurada para {key}.'
            ) from error

    @staticmethod
    def _audit_actor(request):
        auth_user = request.user
        email = getattr(auth_user, 'email', '')
        usuario = None
        if email:
            usuario = Usuario.objects.select_related('id_voluntario').filter(
                id_voluntario__email__iexact=email,
            ).first()
        nome = (
            usuario.id_voluntario.nome
            if usuario
            else auth_user.get_username()
        )
        return usuario, nome

    def save_model(self, request, obj, form, change):
        entidade = self._audit_entity()
        valores_anteriores = {}
        if change:
            existente = self.model._default_manager.filter(pk=obj.pk).first()
            if existente is not None:
                valores_anteriores = snapshot(existente)

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            usuario, usuario_nome = self._audit_actor(request)
            registrar_evento(
                entidade=entidade,
                instancia=obj,
                acao='EDICAO' if change else 'CRIACAO',
                usuario=usuario,
                usuario_nome=usuario_nome,
                resumo=(
                    f'{self.model._meta.verbose_name} "{obj}" '
                    f'{"editado" if change else "cadastrado"} pelo Django Admin.'
                ),
                valores_anteriores=valores_anteriores,
            )

    def delete_model(self, request, obj):
        entidade = self._audit_entity()
        registro_id = obj.pk
        valores_anteriores = snapshot(obj)
        resumo = (
            f'{self.model._meta.verbose_name} "{obj}" excluído pelo Django Admin.'
        )
        with transaction.atomic():
            super().delete_model(request, obj)
            usuario, usuario_nome = self._audit_actor(request)
            registrar_evento(
                entidade=entidade,
                id_registro=registro_id,
                acao='EXCLUSAO',
                usuario=usuario,
                usuario_nome=usuario_nome,
                resumo=resumo,
                valores_anteriores=valores_anteriores,
            )

    def delete_queryset(self, request, queryset):
        entidade = self._audit_entity()
        registros = [
            (obj.pk, snapshot(obj), str(obj))
            for obj in queryset
        ]
        with transaction.atomic():
            super().delete_queryset(request, queryset)
            usuario, usuario_nome = self._audit_actor(request)
            for registro_id, valores_anteriores, descricao in registros:
                registrar_evento(
                    entidade=entidade,
                    id_registro=registro_id,
                    acao='EXCLUSAO',
                    usuario=usuario,
                    usuario_nome=usuario_nome,
                    resumo=(
                        f'{self.model._meta.verbose_name} "{descricao}" '
                        'excluído pelo Django Admin.'
                    ),
                    valores_anteriores=valores_anteriores,
                )
