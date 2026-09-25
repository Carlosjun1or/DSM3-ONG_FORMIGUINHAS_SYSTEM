from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum

# Cadastro de Materiais
class Material(models.Model):
    UNIDADES = [
        ('litro', 'Litro'),
        ('metro', 'Metro'),
        ('quilo', 'Quilo'),
        ('peça', 'Peça'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome")
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    quantidade_inicial = models.IntegerField(default=0, verbose_name="Quantidade inicial")
    unidade = models.CharField(max_length=20, choices=UNIDADES, verbose_name="Unidade")
    is_donativo = models.BooleanField(default=False, verbose_name="É donativo?")
    doador = models.CharField(max_length=100, blank=True, null=True, verbose_name="Doador")

    def __str__(self):
        origem = "Donativo" if self.is_donativo else "Comprado"
        return f"{self.nome} ({self.codigo}) - {origem}"

    @property
    def saldo(self):
        entradas = self.movimentacao_set.filter(tipo='entrada').aggregate(total=Sum('quantidade'))['total'] or 0
        saidas = self.movimentacao_set.filter(tipo='saida').aggregate(total=Sum('quantidade'))['total'] or 0
        return self.quantidade_inicial + entradas - saidas

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materiais"


# Movimentação de Estoque
class Movimentacao(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material")
    tipo = models.CharField(
        max_length=10,
        choices=[('entrada', 'Entrada'), ('saida', 'Saída')],
        verbose_name="Tipo de movimentação"
    )
    quantidade = models.IntegerField(verbose_name="Quantidade")
    data = models.DateTimeField(auto_now_add=True, verbose_name="Data")
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Administrador")

    def __str__(self):
        return f"{self.tipo} - {self.material.nome} ({self.quantidade}) por {self.usuario} em {self.data.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        if self.tipo == 'saida' and self.quantidade > self.material.saldo:
            raise ValueError("Movimentação inválida: saldo insuficiente.")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
        ordering = ['-data']
