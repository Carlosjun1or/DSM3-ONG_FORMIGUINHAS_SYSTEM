from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from acao.models import Acao, AcaoImagem
from praia.models import Praia


@override_settings(USE_L10N=True, LANGUAGE_CODE='pt-br')
class LocalizacaoPraiasTests(TestCase):
    def setUp(self):
        Praia.objects.create(
            nome='Praia de teste',
            cidade='Santos',
            latitude=Decimal('-23.970543'),
            longitude=Decimal('-46.335465'),
            praia_ativa='ATIVA',
        )

    def test_coordenadas_sao_renderizadas_com_ponto_decimal_nas_listas(self):
        for url in (reverse('index'), reverse('praias_atuacao')):
            with self.subTest(url=url):
                resposta = self.client.get(url)

                self.assertContains(
                    resposta,
                    'data-latitude="-23.970543"',
                )
                self.assertContains(
                    resposta,
                    'data-longitude="-46.335465"',
                )


class GaleriaMutiroesTests(TestCase):
    def test_home_organiza_impacto_e_apoio_antes_da_secao_de_praias(self):
        resposta = self.client.get(reverse('index'))
        conteudo = resposta.content.decode()
        posicoes = [
            conteudo.index('class="secao-impacto"'),
            conteudo.index('id="historia"'),
            conteudo.index('id="multiroes"'),
            conteudo.index('id="apoie"'),
            conteudo.index('id="praias"'),
        ]

        self.assertEqual(posicoes, sorted(posicoes))
        self.assertContains(resposta, 'Resultados que fazem a diferença')
        self.assertContains(resposta, 'nossos mutirões limparam praias')
        self.assertContains(resposta, 'encaminharam resíduos')
        self.assertContains(resposta, '1.512 kg')
        self.assertContains(resposta, '132 mil L')
        self.assertContains(resposta, '8.500 kg')
        self.assertContains(resposta, '43.729 mil')
        self.assertContains(resposta, 'data-copiar-pix')

    def test_home_exibe_cartoes_de_mutiroes_realizados_e_proximos(self):
        praia = Praia.objects.create(
            nome='Praia do encontro',
            cidade='Santos',
            latitude=Decimal('-23.970543'),
            longitude=Decimal('-46.335465'),
            praia_ativa='ATIVA',
        )
        realizado = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=timezone.localdate() - timedelta(days=2),
            horario=time(9, 0),
            local='Orla de Santos',
            descricao='Limpeza coletiva da faixa de areia.',
            status=Acao.STATUS_CONCLUIDA,
            praia=praia,
        )
        AcaoImagem.objects.create(
            acao=realizado,
            imagem='acoes/teste/mutirao-gonzaga.jpg',
            descricao='Voluntários recolhendo resíduos na praia',
        )
        Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=timezone.localdate() + timedelta(days=2),
            horario=time(8, 30),
            local='Ponto de encontro na praça',
            descricao='Traga sua garrafa reutilizável.',
            status=Acao.STATUS_PLANEJADA,
            praia=praia,
        )

        resposta = self.client.get(reverse('index'))

        self.assertContains(resposta, 'class="multiroes-destaques"')
        self.assertContains(
            resposta,
            'src="/media/acoes/teste/mutirao-gonzaga.jpg"',
        )
        self.assertContains(
            resposta,
            'alt="Voluntários recolhendo resíduos na praia"',
        )
        self.assertContains(resposta, 'Mutirão realizado')
        self.assertContains(resposta, 'Mutirão agendado')
        self.assertContains(resposta, 'class="proximo-mutirao-data"')
        self.assertContains(resposta, 'Limpeza coletiva da faixa de areia.')
        self.assertContains(resposta, 'Traga sua garrafa reutilizável.')
        self.assertContains(resposta, 'Quero participar')

    def test_filtros_e_paginacao_mantem_os_parametros_selecionados(self):
        praia = Praia.objects.create(
            nome='Praia da paginação',
            cidade='Santos',
            latitude=Decimal('-23.970543'),
            longitude=Decimal('-46.335465'),
            praia_ativa='ATIVA',
        )
        for numero in range(21):
            Acao.objects.create(
                tipo=Acao.TIPO_MUTIRAO,
                data=date(2026, 10, 20),
                horario=time(9, 0),
                local='Orla de Santos',
                descricao=f'Limpeza costeira Gonzaga {numero}',
                status=Acao.STATUS_CONCLUIDA,
                praia=praia,
            )

        parametros = {'busca': 'gonzaga', 'praia': str(praia.pk)}
        primeira_pagina = self.client.get(reverse('multiroes'), parametros)

        self.assertEqual(primeira_pagina.context['pagina'].paginator.count, 21)
        self.assertEqual(primeira_pagina.context['pagina'].paginator.per_page, 20)
        self.assertEqual(primeira_pagina.context['pagina'].number, 1)
        self.assertContains(
            primeira_pagina,
            f'busca=gonzaga&amp;praia={praia.pk}&amp;page=2',
        )
        self.assertContains(
            primeira_pagina,
            'Exibindo 1–20 de 21 mutirões',
            count=1,
        )
        self.assertContains(primeira_pagina, 'value="gonzaga"')
        self.assertContains(primeira_pagina, f'value="{praia.pk}" selected')

        segunda_pagina = self.client.get(
            reverse('multiroes'),
            {**parametros, 'page': '2'},
        )
        self.assertEqual(segunda_pagina.context['pagina'].number, 2)
        self.assertEqual(len(segunda_pagina.context['pagina']), 1)
        self.assertContains(
            segunda_pagina,
            f'busca=gonzaga&amp;praia={praia.pk}&amp;page=1',
        )

    def test_fotos_sao_miniaturas_clicaveis_com_modal_e_navegacao(self):
        praia = Praia.objects.create(
            nome='Praia da galeria',
            cidade='Santos',
            latitude=Decimal('-23.970543'),
            longitude=Decimal('-46.335465'),
            praia_ativa='ATIVA',
        )
        mutirao = Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date(2026, 10, 20),
            horario=time(9, 0),
            local='Praia da galeria',
            status=Acao.STATUS_CONCLUIDA,
            praia=praia,
        )
        for numero in range(1, 6):
            AcaoImagem.objects.create(
                acao=mutirao,
                imagem=f'acoes/demo/foto-{numero}.jpg',
                descricao=f'Foto {numero}',
            )
        Acao.objects.create(
            tipo=Acao.TIPO_MUTIRAO,
            data=date(2026, 10, 21),
            horario=time(9, 0),
            local='Praia da galeria',
            status=Acao.STATUS_CONCLUIDA,
            praia=praia,
        )

        resposta = self.client.get(reverse('multiroes'))

        self.assertContains(resposta, 'class="multirao-foto-abrir"', count=5)
        self.assertContains(resposta, '>Fotos</span>', count=2)
        self.assertContains(resposta, '>Sem fotos</span>')
        self.assertContains(resposta, 'Colagem de fotos do mutirão')
        self.assertContains(resposta, '>5 fotos</span>')
        self.assertContains(resposta, '>+1</span>')
        self.assertContains(resposta, '<figure hidden>', count=1)
        self.assertContains(resposta, 'class="multirao-foto-modal"')
        self.assertContains(resposta, 'data-foto-contexto')
        self.assertContains(resposta, 'Visualização da foto')
        self.assertContains(resposta, 'data-foto-anterior')
        self.assertContains(resposta, 'data-foto-proxima')
        self.assertContains(resposta, 'Sem imagens')
        self.assertLess(
            resposta.content.index(b'class="multirao-card-conteudo"'),
            resposta.content.index(b'class="multirao-galeria"'),
        )
