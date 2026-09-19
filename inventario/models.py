from django.db import models

# 4.1 Cadastro de Materiais
class Material(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    descricao = models.TextField(blank=True)
    quantidade_inicial = models.IntegerField(default=0)
    unidade = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    @property
    def saldo(self):
        entradas = sum(m.quantidade for m in self.movimentacao_set.filter(tipo='entrada'))
        saidas = sum(m.quantidade for m in self.movimentacao_set.filter(tipo='saida'))
        return self.quantidade_inicial + entradas - saidas


# 4.2 Movimentação de Estoque

class Movimentacao(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=[('entrada','Entrada'),('saida','Saída')])
    quantidade = models.IntegerField()
    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo} - {self.material.nome} ({self.quantidade})"

    class Meta:
        verbose_name = "Movimentação"
        verbose_name_plural = "Movimentações"
