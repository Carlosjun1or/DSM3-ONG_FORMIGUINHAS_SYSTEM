import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from usuario.models import Usuario

from .forms import PraiaForm
from .models import Praia


def localizar_praia_view(request):
    usuario = get_session_usuario(request)
    if not usuario or usuario.tipo != 'ADMIN':
        return JsonResponse({'erro': 'Não autorizado.'}, status=403)
    if request.method != 'GET':
        return JsonResponse({'erro': 'Método não permitido.'}, status=405)

    nome = request.GET.get('nome', '').strip()
    cidade = request.GET.get('cidade', '').strip()
    if not nome or not cidade:
        return JsonResponse(
            {'erro': 'Informe o nome da praia e a cidade para localizar.'},
            status=400,
        )

    parametros = urlencode({
        'q': f'{nome}, {cidade}, Brasil',
        'format': 'jsonv2',
        'limit': 1,
        'addressdetails': 0,
    })
    requisicao = Request(
        f'https://nominatim.openstreetmap.org/search?{parametros}',
        headers={
            'User-Agent': 'Formiguinhas-ONG/1.0',
            'Accept-Language': 'pt-BR',
        },
    )

    try:
        with urlopen(requisicao, timeout=10) as resposta:
            resultados = resposta.read().decode('utf-8')
    except (HTTPError, URLError, TimeoutError):
        return JsonResponse(
            {'erro': 'Não foi possível consultar o serviço de localização agora.'},
            status=502,
        )

    try:
        resultado = json.loads(resultados)
        localizacao = resultado[0]
        latitude = float(localizacao['lat'])
        longitude = float(localizacao['lon'])
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return JsonResponse(
            {'erro': 'Localização não encontrada para essa praia e cidade.'},
            status=404,
        )

    return JsonResponse({'latitude': latitude, 'longitude': longitude})


def get_session_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        return Usuario.objects.get(id_usuario=usuario_id)
    except Usuario.DoesNotExist:
        request.session.flush()
        return None


def praias_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')

    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    cidade = request.GET.get('cidade', '').strip()
    praias = Praia.objects.select_related(
        'cadastrado_por__id_voluntario',
        'ultimo_editado_por__id_voluntario',
    ).all().order_by('nome')

    if busca:
        praias = praias.filter(nome__icontains=busca)
    if status in dict(Praia.STATUS_CHOICES):
        praias = praias.filter(praia_ativa=status)
    if cidade:
        praias = praias.filter(cidade__iexact=cidade)

    cidades_unicas = {}
    for cidade_cadastrada in Praia.objects.values_list('cidade', flat=True).order_by('cidade'):
        cidade_limpa = cidade_cadastrada.strip()
        cidades_unicas.setdefault(cidade_limpa.casefold(), cidade_limpa)

    return render(request, 'sistema/praias.html', {
        'usuario': usuario,
        'praias': praias,
        'busca': busca,
        'status_selecionado': status,
        'cidade_selecionada': cidade,
        'cidades': sorted(cidades_unicas.values(), key=str.casefold),
        'status_choices': Praia.STATUS_CHOICES,
        'total_praias': Praia.objects.count(),
        'total_ativas': Praia.objects.filter(praia_ativa='ATIVA').count(),
    })


def cadastrar_praia_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    if request.method == 'POST':
        form = PraiaForm(request.POST)
        if form.is_valid():
            nome = (form.cleaned_data['nome'] or '').strip()
            cidade = (form.cleaned_data['cidade'] or '').strip()

            praia_duplicada = Praia.objects.filter(
                nome__iexact=nome,
                cidade__iexact=cidade,
            ).exists()

            if praia_duplicada:
                messages.error(
                    request,
                    'Praia não cadastrada. Já existe uma praia cadastrada com esse nome e cidade.'
                )
                return render(request, 'sistema/cadastro-praia.html', {
                    'usuario': usuario,
                    'form': form,
                    'modo_edicao': False,
                })

            praia = form.save(commit=False)
            praia.cadastrado_por = usuario
            praia.cadastrado_por_nome = usuario.id_voluntario.nome
            praia.cadastrado_por_tipo = usuario.tipo
            praia.ultimo_editado_por = None
            praia.ultimo_editado_por_nome = None
            praia.ultimo_editado_por_tipo = None
            praia.dt_ultima_edicao = None
            praia.save()
            return redirect('praias')
    else:
        form = PraiaForm()

    return render(request, 'sistema/cadastro-praia.html', {
        'usuario': usuario,
        'form': form,
        'modo_edicao': False,
    })


def editar_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    praia = get_object_or_404(Praia, id_praia=praia_id)
    if request.method == 'POST':
        form = PraiaForm(request.POST, instance=praia)
        if form.is_valid():
            praia = form.save(commit=False)
            praia.ultimo_editado_por = usuario
            praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
            praia.ultimo_editado_por_tipo = usuario.tipo
            praia.dt_ultima_edicao = timezone.now()
            praia.save()
            return redirect('praias')
    else:
        form = PraiaForm(instance=praia)

    return render(request, 'sistema/cadastro-praia.html', {
        'usuario': usuario,
        'form': form,
        'praia': praia,
        'modo_edicao': True,
    })


def atualizar_status_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        status = request.POST.get('praia_ativa')
        if status in dict(Praia.STATUS_CHOICES):
            praia.praia_ativa = status
            praia.ultimo_editado_por = usuario
            praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
            praia.ultimo_editado_por_tipo = usuario.tipo
            praia.dt_ultima_edicao = timezone.now()
            praia.save(update_fields=['praia_ativa', 'ultimo_editado_por', 'ultimo_editado_por_nome', 'ultimo_editado_por_tipo', 'dt_ultima_edicao'])

    return redirect('praias')


def excluir_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return redirect('praias')

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        praia.delete()

    return redirect('praias')
