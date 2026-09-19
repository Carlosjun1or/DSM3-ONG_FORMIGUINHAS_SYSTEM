from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class Praia(models.Model):
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
    ]

    id_praia = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=150)
    cidade = models.CharField(max_length=100)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    praia_ativa = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVA')
    descricao = models.TextField(blank=True)
    cadastrado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='praias_cadastradas',
    )
    cadastrado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    cadastrado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    ultimo_editado_por = models.ForeignKey(
        'usuario.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='praias_editadas',
    )
    ultimo_editado_por_nome = models.CharField(max_length=150, null=True, blank=True)
    ultimo_editado_por_tipo = models.CharField(max_length=20, null=True, blank=True)
    dt_cadastro = models.DateTimeField(auto_now_add=True, null=True)
    dt_ultima_edicao = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'praia'
        verbose_name = 'Praia'
        verbose_name_plural = 'Praias'

    def __str__(self):
        return self.nome
