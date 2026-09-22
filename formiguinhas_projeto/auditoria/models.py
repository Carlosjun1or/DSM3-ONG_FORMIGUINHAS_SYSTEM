from django.db import models


class EventoAuditoria(models.Model):
    ENTIDADE_LABELS = {
        'USUARIO': 'Usuário', 'VOLUNTARIO': 'Voluntário', 'PRAIA': 'Praia',
        'EQUIPE': 'Equipe', 'EQUIPE_MEMBRO': 'Membro de equipe', 'ACAO': 'Ação',
        'CONDOMINIO': 'Condomínio', 'BAG': 'Bag', 'MOVIMENTACAO': 'Movimentação de bag',
    }
    ACAO_CHOICES = [
        ('CRIACAO', 'Criação'), ('EDICAO', 'Edição'), ('MUDANCA_STATUS', 'Mudança de status'),
        ('VINCULO', 'Vínculo'), ('EXCLUSAO', 'Exclusão'), ('MOVIMENTACAO', 'Movimentação'),
    ]
    entidade = models.CharField(max_length=40)
    id_registro = models.PositiveIntegerField(null=True, blank=True)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    usuario = models.ForeignKey('usuario.Usuario', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='eventos_auditoria')
    usuario_nome = models.CharField(max_length=150, blank=True)
    data_evento = models.DateTimeField(auto_now_add=True)
    resumo = models.CharField(max_length=255)
    valores_anteriores = models.JSONField(default=dict, blank=True)
    valores_novos = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-data_evento', '-id')
        indexes = [
            models.Index(fields=('entidade', 'acao')),
            models.Index(fields=('data_evento',)),
            models.Index(fields=('usuario',)),
        ]

    def __str__(self):
        return f'{self.entidade} #{self.id_registro} - {self.get_acao_display()}'

    def get_entidade_display(self):
        return self.ENTIDADE_LABELS.get(self.entidade, self.entidade.replace('_', ' ').title())
