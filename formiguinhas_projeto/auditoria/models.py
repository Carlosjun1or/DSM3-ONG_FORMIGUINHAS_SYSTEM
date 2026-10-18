from django.db import models


class EventoAuditoria(models.Model):
    ENTIDADE_LABELS = {
        'USUARIO': 'Usuário', 'VOLUNTARIO': 'Voluntário', 'PRAIA': 'Praia',
        'EQUIPE': 'Equipe', 'EQUIPE_MEMBRO': 'Membro de equipe', 'ACAO': 'Ação',
        'ACAO_EQUIPE': 'Equipe vinculada à ação',
        'ACAO_PARTICIPANTE': 'Participante da ação',
        'ACAO_RESPONSAVEL': 'Responsável pela ação',
        'ACAO_PARTICIPANTE_HISTORICO': 'Histórico de participante da ação',
        'COMUNICADO_PRAIA': 'Praia relacionada ao comunicado',
        'COMUNICADO_EQUIPE': 'Equipe relacionada ao comunicado',
        'COMUNICADO_ACAO': 'Ação relacionada ao comunicado',
        'COMUNICADO_DOACAO': 'Doação relacionada ao comunicado',
        'DOACAO_FINANCEIRA': 'Detalhe de doação financeira',
        'ITEM_DOACAO_MATERIAL': 'Item de doação de material',
        'ACAO_IMAGEM': 'Imagem da ação',
        'CONDOMINIO': 'Condomínio', 'BAG': 'Bag', 'MOVIMENTACAO': 'Movimentação de bag',
        'COMUNICADO': 'Comunicado', 'TEMA_COMUNICADO': 'Tema de comunicado',
        'COMUNICADO_LEITURA': 'Leitura de comunicado',
        'RESIDUO': 'Resíduo coletado', 'DESTINACAO_RESIDUO': 'Destinação de resíduo',
        'COLETA_RESIDUO': 'Coleta de resíduos',
        'ITEM_COLETA_RESIDUO': 'Item de coleta de resíduos',
        'DOADOR': 'Doador',
        'DOACAO': 'Doação',
        'MATERIAL': 'Material',
        'MOVIMENTACAO_ESTOQUE': 'Movimentação de estoque',
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


class EstadoLeituraAuditoria(models.Model):
    usuario = models.OneToOneField(
        'usuario.Usuario',
        on_delete=models.CASCADE,
        related_name='estado_leitura_auditoria',
    )
    ultimo_evento_id = models.PositiveIntegerField(default=0)
