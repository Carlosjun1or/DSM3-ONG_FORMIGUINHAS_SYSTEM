from django.db import models
from django.db.models import Q
from django.utils import timezone

from usuario.models import Usuario, Voluntario


class Equipe(models.Model):
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
    ]

    id_equipe = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=150)
    praia = models.ForeignKey(
        'praia.Praia',
        on_delete=models.PROTECT,
        related_name='equipes',
        null=True,
        blank=True,
    )
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ATIVA')
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipes_cadastradas',
    )
    cadastrado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    cadastrado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipes_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    ultimo_editado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'equipe'
        verbose_name = 'Equipe'
        verbose_name_plural = 'Equipes'
        ordering = ('nome',)

    def __str__(self):
        return self.nome


class EquipeMembro(models.Model):
    PAPEL_VOLUNTARIO = 'VOLUNTARIO'
    PAPEL_COORDENADOR = 'COORDENADOR'
    PAPEL_CHOICES = [
        (PAPEL_VOLUNTARIO, 'Voluntário'),
        (PAPEL_COORDENADOR, 'Coordenador'),
    ]
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
    ]

    id_equipe_membro = models.AutoField(primary_key=True)
    equipe = models.ForeignKey(Equipe, on_delete=models.PROTECT, related_name='membros')
    voluntario = models.ForeignKey(Voluntario, on_delete=models.PROTECT, related_name='equipes')
    papel = models.CharField(max_length=15, choices=PAPEL_CHOICES, default='VOLUNTARIO')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ATIVO')
    dt_entrada = models.DateTimeField(default=timezone.now)
    dt_saida = models.DateTimeField(null=True, blank=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True)
    cadastrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='membros_equipe_cadastrados',
    )
    cadastrado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    cadastrado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='membros_equipe_editados',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    ultimo_editado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'equipe_membro'
        verbose_name = 'Membro da equipe'
        verbose_name_plural = 'Membros da equipe'
        ordering = ('equipe', 'voluntario')
        constraints = [
            models.UniqueConstraint(
                fields=('equipe', 'voluntario'),
                condition=Q(status='ATIVO'),
                name='unico_membro_ativo_por_equipe',
            ),
        ]

    def __str__(self):
        return f'{self.voluntario.nome} - {self.equipe.nome}'
