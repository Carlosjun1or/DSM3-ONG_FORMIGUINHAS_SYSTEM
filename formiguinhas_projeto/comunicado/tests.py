from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from usuario.models import Usuario, Voluntario

from .context_processors import notificacoes_comunicados
from .models import Comunicado, ComunicadoLeitura
from .services import desarquivar
from .views import interno_detalhe, internos


class ComunicadoLeituraTests(TestCase):
    def setUp(self):
        voluntario = Voluntario.objects.create(
            nome='Coordenador de teste',
            dt_nascimento=date(1990, 1, 1),
            endereco='Rua de teste',
            telefone='11999999999',
            email='coordenador-teste@example.com',
        )
        self.usuario = Usuario.objects.create(
            id_voluntario=voluntario,
            tipo='COORDENADOR',
            senha='senha',
        )
        self.session = self.client.session
        self.session['usuario_id'] = self.usuario.id_usuario
        self.session['usuario_tipo'] = self.usuario.tipo
        self.session['usuario_nome'] = voluntario.nome
        self.session.save()
        self.client.cookies['sessionid'] = self.session.session_key

    def criar_comunicado(self, titulo):
        return Comunicado.objects.create(
            tipo=Comunicado.AVISO,
            titulo=titulo,
            conteudo='Conteúdo de teste',
            publico=Comunicado.TODOS,
            status=Comunicado.PUBLICADO,
            dt_publicacao=timezone.now(),
        )

    def test_sino_conta_apenas_comunicados_nao_lidos(self):
        self.criar_comunicado('Aviso não lido')
        outro = self.criar_comunicado('Aviso lido')
        ComunicadoLeitura.objects.create(comunicado=outro, usuario=self.usuario)

        request = RequestFactory().get('/')
        request.session = self.session
        contexto = notificacoes_comunicados(request)

        self.assertEqual(contexto['comunicados_nao_lidos_count'], 1)
        self.assertEqual(contexto['comunicados_vigentes_count'], 2)

    def test_abrir_central_marca_comunicados_visiveis_como_lidos(self):
        primeiro = self.criar_comunicado('Primeiro aviso')
        segundo = self.criar_comunicado('Segundo aviso')

        request = RequestFactory().get(reverse('central_comunicados'))
        request.session = self.session
        response = internos(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ComunicadoLeitura.objects.filter(usuario=self.usuario).count(),
            2,
        )
        self.assertEqual(
            ComunicadoLeitura.objects.filter(
                usuario=self.usuario,
                comunicado__in=[primeiro, segundo],
            ).count(),
            2,
        )

    def test_abrir_detalhe_marca_apenas_o_comunicado(self):
        comunicado = self.criar_comunicado('Aviso detalhado')
        outro = self.criar_comunicado('Outro aviso')

        request = RequestFactory().get(
            reverse('comunicado_interno_detalhe', args=[comunicado.id_comunicado])
        )
        request.session = self.session
        response = interno_detalhe(request, comunicado.id_comunicado)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ComunicadoLeitura.objects.filter(
                usuario=self.usuario,
                comunicado=comunicado,
            ).exists()
        )
        self.assertFalse(
            ComunicadoLeitura.objects.filter(
                usuario=self.usuario,
                comunicado=outro,
            ).exists()
        )

    def test_desarquivar_retorna_comunicado_para_rascunho(self):
        comunicado = self.criar_comunicado('Aviso arquivado')
        comunicado.status = Comunicado.ARQUIVADO
        comunicado.save(update_fields=('status',))

        desarquivar(comunicado, self.usuario)

        comunicado.refresh_from_db()
        self.assertEqual(comunicado.status, Comunicado.RASCUNHO)
