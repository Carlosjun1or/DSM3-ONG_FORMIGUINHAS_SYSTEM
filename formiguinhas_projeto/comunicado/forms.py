from django import forms
from acao.models import Acao
from doacao.models import Doacao
from equipe.models import Equipe
from praia.models import Praia
from .models import Comunicado, Tema


class ComunicadoForm(forms.ModelForm):
    praias = forms.ModelMultipleChoiceField(
        queryset=Praia.objects.none(), required=False, label='Praias relacionadas',
        help_text='Opcional. Selecione uma ou mais praias.',
        widget=forms.SelectMultiple(attrs={'class': 'form-control relationship-select', 'size': 6}),
    )
    equipes = forms.ModelMultipleChoiceField(
        queryset=Equipe.objects.none(), required=False, label='Equipes relacionadas',
        help_text='Opcional. Ao selecionar uma equipe, a praia vinculada será adicionada.',
        widget=forms.SelectMultiple(attrs={'class': 'form-control relationship-select', 'size': 6}),
    )
    acoes = forms.ModelMultipleChoiceField(
        queryset=Acao.objects.none(), required=False, label='Ações relacionadas',
        help_text='Opcional. A ação adiciona a praia, as equipes participantes e os resíduos já registrados nela.',
        widget=forms.SelectMultiple(attrs={'class': 'form-control relationship-select', 'size': 6}),
    )
    doacoes = forms.ModelMultipleChoiceField(
        queryset=Doacao.objects.none(), required=False, label='Doações relacionadas',
        help_text='Opcional. Selecione doações para relacionar a este comunicado.',
        widget=forms.SelectMultiple(attrs={'class': 'form-control relationship-select', 'size': 6}),
    )

    class Meta:
        model = Comunicado
        fields = ('tipo', 'titulo', 'resumo', 'conteudo', 'publico', 'tema',
                  'duracao_expiracao', 'unidade_duracao_expiracao',
                  'praias', 'equipes', 'acoes', 'doacoes')
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Mutirão de limpeza no Boqueirão',
            }),
            'resumo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descreva a informação em uma frase curta (opcional)',
            }),
            'conteudo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Escreva aqui a mensagem completa do comunicado.',
            }),
            'publico': forms.Select(attrs={'class': 'form-control'}),
            'tema': forms.Select(attrs={'class': 'form-control'}),
            'praias': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
            'equipes': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
            'acoes': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5}),
        }
        labels = {
            'tipo': 'Tipo de comunicado',
            'titulo': 'Título',
            'resumo': 'Resumo',
            'conteudo': 'Conteúdo',
            'publico': 'Público do aviso',
            'tema': 'Tema da notícia',
            'duracao_expiracao': 'Expirar depois de',
            'unidade_duracao_expiracao': 'Unidade do prazo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tema'].queryset = Tema.objects.filter(ativo=True).order_by('nome')
        self.fields['tema'].required = False
        self.fields['tema'].empty_label = 'Selecione um tema'
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de comunicado'),
            *Comunicado.TIPO_CHOICES,
        ]
        self.fields['publico'].choices = [
            ('', 'Selecione o público do aviso'),
            *Comunicado.PUBLICO_CHOICES,
        ]
        self.fields['resumo'].required = False
        self.fields['tipo'].help_text = 'Escolha Aviso para comunicação interna ou Notícia para o site.'
        self.fields['titulo'].help_text = 'Use um título curto e fácil de identificar.'
        self.fields['conteudo'].help_text = 'Informe a mensagem completa, com data, local ou orientação quando necessário.'
        self.fields['publico'].help_text = 'Notícias são sempre exibidas para todos.'
        self.fields['duracao_expiracao'].required = False
        self.fields['duracao_expiracao'].widget = forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1,
            'step': 1,
            'placeholder': 'Ex.: 4',
        })
        self.fields['duracao_expiracao'].help_text = (
            'Opcional. O prazo começa a contar automaticamente quando o comunicado for publicado.'
        )
        self.fields['unidade_duracao_expiracao'].required = False
        self.fields['unidade_duracao_expiracao'].choices = [
            ('', 'Selecione a unidade'),
            *Comunicado.UNIDADE_DURACAO_CHOICES,
        ]
        self.fields['unidade_duracao_expiracao'].widget.attrs['class'] = 'form-control'
        self.fields['praias'].queryset = Praia.objects.filter(
            praia_ativa='ATIVA'
        ).order_by('nome')
        self.fields['equipes'].queryset = Equipe.objects.filter(
            status='ATIVA'
        ).order_by('nome')
        self.fields['acoes'].queryset = Acao.objects.select_related('praia').order_by('-data')
        self.fields['doacoes'].queryset = Doacao.objects.select_related(
            'doador',
        ).order_by('-data_recebimento', '-id_doacao')
        self.fields['praias'].label_from_instance = lambda praia: f'{praia.nome} - {praia.cidade}'
        self.fields['equipes'].label_from_instance = lambda equipe: (
            f'{equipe.nome} - {equipe.praia.nome}' if equipe.praia else f'{equipe.nome} - sem praia'
        )
        self.fields['acoes'].label_from_instance = lambda acao: (
            f'{acao.get_tipo_display()} - {acao.praia.nome} ({acao.data.strftime("%d/%m/%Y")})'
        )
        self.fields['doacoes'].label_from_instance = self.rotulo_doacao
        if self.instance and self.instance.pk:
            self.initial['praias'] = self.instance.praias.values_list('praia_id', flat=True)
            self.initial['equipes'] = self.instance.equipes.values_list('equipe_id', flat=True)
            self.initial['acoes'] = self.instance.acoes.values_list('acao_id', flat=True)
            self.initial['doacoes'] = self.instance.doacoes.values_list('doacao_id', flat=True)

    @staticmethod
    def rotulo_doacao(doacao):
        doador = 'Anônima' if doacao.anonima else (
            doacao.doador.nome if doacao.doador_id else 'Doador não informado'
        )
        return (
            f'Doação #{doacao.id_doacao} - {doacao.data_recebimento:%d/%m/%Y} - '
            f'{doacao.get_tipo_display()} - {doador}'
        )

    def clean(self):
        data = super().clean()
        tipo = data.get('tipo')
        if tipo == Comunicado.NOTICIA:
            data['publico'] = Comunicado.TODOS
        elif tipo == Comunicado.AVISO:
            if data.get('tema'):
                self.add_error('tema', 'Avisos não podem ter tema.')
            if data.get('publico') not in dict(Comunicado.PUBLICO_CHOICES):
                self.add_error('publico', 'Selecione o público do aviso.')
        duracao = data.get('duracao_expiracao')
        unidade = data.get('unidade_duracao_expiracao')
        if duracao and not unidade:
            self.add_error('unidade_duracao_expiracao', 'Selecione semanas, meses ou anos.')
        if unidade and not duracao:
            self.add_error('duracao_expiracao', 'Informe a quantidade do prazo.')
        if duracao is not None and duracao <= 0:
            self.add_error('duracao_expiracao', 'Informe uma quantidade maior que zero.')
        return data


class TemaForm(forms.ModelForm):
    class Meta:
        model = Tema
        fields = ('nome', 'descricao', 'ativo')
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Educação ambiental',
                'autocomplete': 'off',
            }),
            'descricao': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Explique brevemente o assunto deste tema (opcional).',
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'topic-active-checkbox'}),
        }
        labels = {
            'nome': 'Nome do tema',
            'descricao': 'Descrição',
            'ativo': 'Tema ativo',
        }

    def clean_nome(self):
        nome = ' '.join(self.cleaned_data['nome'].split())
        duplicado = Tema.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if duplicado.exists():
            raise forms.ValidationError('Já existe um tema com esse nome.')
        return nome
