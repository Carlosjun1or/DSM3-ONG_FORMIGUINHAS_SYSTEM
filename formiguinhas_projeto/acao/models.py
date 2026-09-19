from django.db import models

from equipe.models import Equipe
from praia.models import Praia
from usuario.models import Usuario, Voluntario


class Acao(models.Model):
    TIPO_MUTIRAO = 'MUTIRAO'
    TIPO_COLETA_VOLUNTARIA = 'COLETA_VOLUNTARIA'
    TIPO_CHOICES = [
        (TIPO_MUTIRAO, 'Mutirão'),
        (TIPO_COLETA_VOLUNTARIA, 'Coleta voluntária'),
    ]

    STATUS_PLANEJADA = 'PLANEJADA'
    STATUS_EM_ANDAMENTO = 'EM_ANDAMENTO'
    STATUS_CONCLUIDA = 'CONCLUIDA'
    STATUS_CANCELADA = 'CANCELADA'
    STATUS_CHOICES = [
        (STATUS_PLANEJADA, 'Planejada'),
        (STATUS_EM_ANDAMENTO, 'Em andamento'),
        (STATUS_CONCLUIDA, 'Concluída'),
        (STATUS_CANCELADA, 'Cancelada'),
    ]

    id_acao = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    data = models.DateField()
    horario = models.TimeField(blank=True, null=True)
    local = models.CharField(max_length=255, blank=True, default='')
    descricao = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANEJADA)
    imagens = models.JSONField(default=list, blank=True)
    praia = models.ForeignKey(Praia, on_delete=models.PROTECT, related_name='acoes')
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acoes_cadastradas',
    )
    cadastrado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    cadastrado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acoes_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    ultimo_editado_por_tipo = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'acao'
        verbose_name = 'Ação'
        verbose_name_plural = 'Ações'
        ordering = ('-data', 'horario')

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.praia} - {self.data}'


class AcaoEquipe(models.Model):
    id_acao_equipe = models.AutoField(primary_key=True)
    acao = models.ForeignKey(Acao, on_delete=models.CASCADE, related_name='equipes_vinculadas')
    equipe = models.ForeignKey(Equipe, on_delete=models.PROTECT, related_name='acoes_vinculadas')

    class Meta:
        db_table = 'acao_equipe'
        verbose_name = 'Equipe da ação'
        verbose_name_plural = 'Equipes da ação'
        unique_together = ('acao', 'equipe')

    def __str__(self):
        return f'{self.acao} / {self.equipe}'


class AcaoParticipante(models.Model):
    STATUS_PENDENTE = 'PENDENTE'
    STATUS_CONFIRMADO = 'CONFIRMADO'
    STATUS_RECUSADO = 'RECUSADO'
    STATUS_PRESENTE = 'PRESENTE'
    STATUS_NAO_COMPARECEU = 'NAO_COMPARECEU'
    STATUS_CHOICES = [
        (STATUS_PENDENTE, 'Pendente'),
        (STATUS_CONFIRMADO, 'Confirmado'),
        (STATUS_RECUSADO, 'Recusado'),
        (STATUS_PRESENTE, 'Presente'),
        (STATUS_NAO_COMPARECEU, 'Não compareceu'),
    ]

    id_acao_participante = models.AutoField(primary_key=True)
    acao = models.ForeignKey(Acao, on_delete=models.CASCADE, related_name='participantes')
    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT, related_name='acoes_participadas')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    compareceu = models.BooleanField(default=False)
    observacao = models.TextField(blank=True, default='')
    dt_confirmacao = models.DateTimeField(null=True, blank=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'acao_participante'
        verbose_name = 'Participante da ação'
        verbose_name_plural = 'Participantes da ação'
        unique_together = ('acao', 'voluntario')

    def __str__(self):
        return f'{self.voluntario.nome} - {self.acao}'


class AcaoParticipanteHistorico(models.Model):
    id_historico = models.AutoField(primary_key=True)
    acao = models.ForeignKey(
        Acao,
        on_delete=models.CASCADE,
        related_name='historico_participantes',
    )
    voluntario = models.ForeignKey(
        Voluntario,
        on_delete=models.PROTECT,
        related_name='historico_acoes_participadas',
    )
    status = models.CharField(max_length=20, choices=AcaoParticipante.STATUS_CHOICES)
    compareceu = models.BooleanField(default=False)
    observacao = models.TextField(blank=True, default='')
    dt_cadastro = models.DateTimeField()
    dt_movimentacao = models.DateTimeField(auto_now_add=True)
    movido_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historicos_participantes_movidos',
    )
    movido_por_nome = models.CharField(max_length=150, null=True, blank=True)
    movido_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    restaurado = models.BooleanField(default=False)
    restaurado_em = models.DateTimeField(null=True, blank=True)
    restaurado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historicos_participantes_restaurados',
    )
    restaurado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    restaurado_por_tipo = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'acao_participante_historico'
        verbose_name = 'Histórico de participante da ação'
        verbose_name_plural = 'Histórico de participantes da ação'
        ordering = ('-dt_movimentacao', 'voluntario__nome')

    def __str__(self):
        return f'{self.voluntario.nome} - {self.acao} ({self.get_status_display()})'


class AcaoResponsavel(models.Model):
    PAPEL_COORDENADOR = 'COORDENADOR'
    PAPEL_RESPONSAVEL = 'RESPONSAVEL'
    PAPEL_CHOICES = [
        (PAPEL_COORDENADOR, 'Coordenador'),
        (PAPEL_RESPONSAVEL, 'Responsável'),
    ]

    id_acao_responsavel = models.AutoField(primary_key=True)
    acao = models.ForeignKey(Acao, on_delete=models.CASCADE, related_name='responsaveis')
    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT, related_name='acoes_responsavel')
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_RESPONSAVEL)

    class Meta:
        db_table = 'acao_responsavel'
        verbose_name = 'Responsável pela ação'
        verbose_name_plural = 'Responsáveis pela ação'
        unique_together = ('acao', 'voluntario')

    def __str__(self):
        return f'{self.voluntario.nome} - {self.acao}'


def adicionar_participantes_automaticos_para_mutirao(acao):
    if acao.tipo != Acao.TIPO_MUTIRAO:
        return []

    voluntarios_automaticos = set()
    for vinculada in acao.equipes_vinculadas.select_related('equipe__praia'):
        membros = vinculada.equipe.membros.select_related('voluntario').filter(status='ATIVO')
        for membro in membros:
            voluntarios_automaticos.add(membro.voluntario_id)

    cadastrados = []
    for voluntario_id in sorted(voluntarios_automaticos):
        participante, created = AcaoParticipante.objects.get_or_create(
            acao=acao,
            voluntario_id=voluntario_id,
            defaults={'status': AcaoParticipante.STATUS_PENDENTE},
        )
        if created:
            participante.status = AcaoParticipante.STATUS_PENDENTE
            participante.save(update_fields=['status'])
        cadastrados.append(participante)

    return cadastrados
