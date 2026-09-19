from django.shortcuts import render
from .models import Material, Movimentacao

def consulta_estoque(request):
    materiais = Material.objects.all()
    return render(request, 'inventario/consulta.html', {'materiais': materiais})

def historico_movimentacoes(request):
    movimentacoes = Movimentacao.objects.all()

    # Filtro por material
    material_id = request.GET.get('material')
    if material_id:
        movimentacoes = movimentacoes.filter(material_id=material_id)

    # Filtro por tipo
    tipo = request.GET.get('tipo')
    if tipo:
        movimentacoes = movimentacoes.filter(tipo=tipo)

    # Filtro por período
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    if data_inicio and data_fim:
        movimentacoes = movimentacoes.filter(data__range=[data_inicio, data_fim])

    movimentacoes = movimentacoes.order_by('-data')
    materiais = Material.objects.all()

    return render(request, 'inventario/historico.html', {
        'movimentacoes': movimentacoes,
        'materiais': materiais
    })
