import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from usuario.models import Usuario
from usuario.views import render_acesso_bloqueado
from usuario.paginacao import paginar_queryset

from .forms import PraiaForm
from .models import Praia
from auditoria.services import registrar_evento, snapshot


def _consultar_nominatim(termo, timeout=7):
    """Consulta o serviço Nominatim (OpenStreetMap) com cabeçalhos adequados."""
    parametros = urlencode({
        'q': termo,
        'format': 'jsonv2',
        'limit': 1,
        'addressdetails': 0,
    })
    requisicao = Request(
        f'https://nominatim.openstreetmap.org/search?{parametros}',
        headers={
            'User-Agent': 'Formiguinhas-ONG/1.0',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        },
    )
    with urlopen(requisicao, timeout=timeout) as resposta:
        corpo = resposta.read().decode('utf-8')
        dados = json.loads(corpo)
        if isinstance(dados, list) and len(dados) > 0:
            item = dados[0]
            return float(item['lat']), float(item['lon'])
    return None


def _consultar_photon(termo, timeout=5):
    """Provedor secundário baseado em OpenStreetMap (Photon / Komoot)."""
    parametros = urlencode({
        'q': termo,
        'limit': 1,
    })
    requisicao = Request(
        f'https://photon.komoot.io/api/?{parametros}',
        headers={
            'User-Agent': 'Formiguinhas-ONG/1.0',
            'Accept-Language': 'pt-BR',
        },
    )
    with urlopen(requisicao, timeout=timeout) as resposta:
        corpo = resposta.read().decode('utf-8')
        dados = json.loads(corpo)
        features = dados.get('features', [])
        if features:
            coords = features[0].get('geometry', {}).get('coordinates', [])
            if len(coords) >= 2:
                # GeoJSON padrão: [longitude, latitude]
                return float(coords[1]), float(coords[0])
    return None


def localizar_praia_view(request):
    usuario = get_session_usuario(request)
    if not usuario or usuario.tipo not in ('ADMIN', 'COORDENADOR'):
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

    # 1. Gerar variações do nome para cobrir diferentes convenções do mapa
    nome_sem_prefixo = re.sub(
        r'^(praia\s+(da|do|de|das|dos)?\s*)',
        '',
        nome,
        flags=re.IGNORECASE,
    ).strip()

    candidatos = [f'{nome}, {cidade}, Brasil']
    if nome_sem_prefixo and nome_sem_prefixo.casefold() != nome.casefold():
        candidatos.append(f'{nome_sem_prefixo}, {cidade}, Brasil')
        candidatos.append(f'Praia {nome_sem_prefixo}, {cidade}, Brasil')
        candidatos.append(f'Praia do {nome_sem_prefixo}, {cidade}, Brasil')
        candidatos.append(f'Praia de {nome_sem_prefixo}, {cidade}, Brasil')
        candidatos.append(f'Praia da {nome_sem_prefixo}, {cidade}, Brasil')
    else:
        candidatos.append(f'Praia {nome}, {cidade}, Brasil')
        candidatos.append(f'Praia do {nome}, {cidade}, Brasil')
        candidatos.append(f'Praia de {nome}, {cidade}, Brasil')
        candidatos.append(f'Praia da {nome}, {cidade}, Brasil')

    # Deduplicar preservando a ordem de busca
    termos_busca = []
    vistos = set()
    for c in candidatos:
        c_norm = c.casefold()
        if c_norm not in vistos:
            vistos.add(c_norm)
            termos_busca.append(c)

    teve_erro_conexao = False

    # 2. Tentar provedor primário: Nominatim (OpenStreetMap)
    for termo in termos_busca:
        try:
            coords = _consultar_nominatim(termo)
            if coords:
                return JsonResponse({'latitude': coords[0], 'longitude': coords[1]})
        except (HTTPError, URLError, TimeoutError):
            teve_erro_conexao = True
            break
        except (ValueError, KeyError, IndexError, json.JSONDecodeError):
            continue

    # 3. Fallback: Provedor secundário Photon (Komoot / OSM)
    for termo in termos_busca:
        try:
            coords = _consultar_photon(termo)
            if coords:
                return JsonResponse({'latitude': coords[0], 'longitude': coords[1]})
        except Exception:
            continue

    # 4. Fallback de cidade: centralizar na cidade para o usuário posicionar o pino
    try:
        coords_cidade = _consultar_photon(f'{cidade}, Brasil') or _consultar_nominatim(f'{cidade}, Brasil')
        if coords_cidade:
            return JsonResponse({
                'latitude': coords_cidade[0],
                'longitude': coords_cidade[1],
                'aviso': f'Praia específica não encontrada; mapa centralizado em {cidade}. Posicione o marcador no ponto desejado.',
            })
    except Exception:
        pass

    if teve_erro_conexao:
        return JsonResponse(
            {'erro': 'Não foi possível consultar o serviço de localização agora.'},
            status=502,
        )

    return JsonResponse(
        {'erro': 'Localização não encontrada para essa praia e cidade.'},
        status=404,
    )


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
    praia_id = request.GET.get('praia', '').strip()
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
    praia_destacada = None
    if praia_id.isdigit():
        praia_destacada = int(praia_id)
        praias = praias.filter(id_praia=praia_destacada)

    cidades_unicas = {}
    for cidade_cadastrada in Praia.objects.values_list('cidade', flat=True).order_by('cidade'):
        cidade_limpa = cidade_cadastrada.strip()
        cidades_unicas.setdefault(cidade_limpa.casefold(), cidade_limpa)

    pagina, filtros_query = paginar_queryset(request, praias)
    return render(request, 'sistema/praias.html', {
        'usuario': usuario,
        'praias': pagina.object_list,
        'pagina': pagina,
        'filtros_query': filtros_query,
        'busca': busca,
        'status_selecionado': status,
        'cidade_selecionada': cidade,
        'praia_destacada': praia_destacada,
        'cidades': sorted(cidades_unicas.values(), key=str.casefold),
        'status_choices': Praia.STATUS_CHOICES,
        'total_praias': Praia.objects.count(),
        'total_ativas': Praia.objects.filter(praia_ativa='ATIVA').count(),
    })


@transaction.atomic
def cadastrar_praia_view(request):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

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
            registrar_evento(entidade='PRAIA', instancia=praia, acao='CRIACAO', usuario=usuario,
                             resumo=f'Praia "{praia.nome}" cadastrada.')
            return redirect('praias')
    else:
        form = PraiaForm()

    return render(request, 'sistema/cadastro-praia.html', {
        'usuario': usuario,
        'form': form,
        'modo_edicao': False,
    })


@transaction.atomic
def editar_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    praia = get_object_or_404(Praia, id_praia=praia_id)
    valores_anteriores = snapshot(praia)
    if request.method == 'POST':
        form = PraiaForm(request.POST, instance=praia)
        if form.is_valid():
            praia = form.save(commit=False)
            praia.ultimo_editado_por = usuario
            praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
            praia.ultimo_editado_por_tipo = usuario.tipo
            praia.dt_ultima_edicao = timezone.now()
            praia.save()
            registrar_evento(entidade='PRAIA', instancia=praia, acao='EDICAO', usuario=usuario,
                             resumo=f'Praia "{praia.nome}" editada.',
                             valores_anteriores=valores_anteriores)
            return redirect('praias')
    else:
        form = PraiaForm(instance=praia)

    return render(request, 'sistema/cadastro-praia.html', {
        'usuario': usuario,
        'form': form,
        'praia': praia,
        'modo_edicao': True,
    })


@transaction.atomic
def atualizar_status_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        anterior = snapshot(praia)
        status = request.POST.get('praia_ativa')
        if status in dict(Praia.STATUS_CHOICES):
            praia.praia_ativa = status
            praia.ultimo_editado_por = usuario
            praia.ultimo_editado_por_nome = usuario.id_voluntario.nome
            praia.ultimo_editado_por_tipo = usuario.tipo
            praia.dt_ultima_edicao = timezone.now()
            praia.save(update_fields=['praia_ativa', 'ultimo_editado_por', 'ultimo_editado_por_nome', 'ultimo_editado_por_tipo', 'dt_ultima_edicao'])
            registrar_evento(entidade='PRAIA', instancia=praia, acao='MUDANCA_STATUS', usuario=usuario,
                             resumo=f'Status da praia "{praia.nome}" alterado.',
                             valores_anteriores=anterior)

    return redirect('praias')


@transaction.atomic
def excluir_praia_view(request, praia_id):
    usuario = get_session_usuario(request)
    if not usuario:
        return redirect('login')
    if usuario.tipo != 'ADMIN':
        return render_acesso_bloqueado(request)

    if request.method == 'POST':
        praia = get_object_or_404(Praia, id_praia=praia_id)
        anterior = snapshot(praia)
        praia.delete()
        registrar_evento(entidade='PRAIA', id_registro=praia_id, acao='EXCLUSAO', usuario=usuario,
                          resumo=f'Praia "{anterior.get("nome", praia_id)}" excluída.',
                          valores_anteriores=anterior)

    return redirect('praias')
