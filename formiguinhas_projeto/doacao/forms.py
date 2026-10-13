from django import forms
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from acao.models import Acao
from estoque.models import Material
from praia.models import Praia

from .models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial


class DoadorForm(forms.ModelForm):
    class Meta:
        model = Doador
        fields = ['tipo', 'nome', 'documento', 'email', 'telefone', 'voluntario', 'ativo']
        labels = {
            'tipo': 'Tipo de doador',
            'nome': 'Nome completo ou razão social',
            'documento': 'CPF ou CNPJ',
            'email': 'E-mail',
            'telefone': 'Telefone',
            'voluntario': 'Voluntário relacionado',
            'ativo': 'Doador ativo',
        }
        help_texts = {
            'tipo': 'Escolha se o cadastro representa uma pessoa ou uma empresa.',
            'nome': 'Use o nome que deve aparecer nos registros e relatórios.',
            'email': 'Informe pelo menos um contato: e-mail ou telefone.',
            'telefone': 'Informe um telefone para contato, se preferir.',
            'voluntario': 'Opcional. Use somente quando o doador também for voluntário.',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Maria da Silva ou Empresa Exemplo Ltda.',
                'autocomplete': 'name',
            }),
            'documento': forms.TextInput(attrs={
                'class': 'form-control documento-input',
                'placeholder': 'CPF: 000.000.000-00 ou CNPJ: 00.000.000/0000-00',
                'inputmode': 'numeric',
                'maxlength': '18',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control email-input',
                'placeholder': 'Ex.: contato@exemplo.com',
                'autocomplete': 'email',
                'inputmode': 'email',
                'maxlength': '254',
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control telefone-input',
                'placeholder': 'Ex.: (11) 99999-9999',
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'maxlength': '15',
            }),
            'voluntario': forms.Select(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voluntario'].queryset = (
            self.fields['voluntario'].queryset.select_related('usuario').order_by('nome')
        )
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de doador'),
            *Doador.TIPO_CHOICES,
        ]
        self.fields['documento'].widget.attrs['maxlength'] = '18'
        self.fields['telefone'].widget.attrs['maxlength'] = '15'
        self.fields['voluntario'].required = False
        self.fields['voluntario'].empty_label = 'Não vincular a voluntário'
        self.fields['voluntario'].label_from_instance = (
            lambda voluntario: f'{voluntario.nome} - {voluntario.email}'
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('email'):
            cleaned['email'] = cleaned['email'].strip().lower()
        if cleaned.get('telefone'):
            cleaned['telefone'] = cleaned['telefone'].strip()
        if not cleaned.get('nome', '').strip():
            self.add_error('nome', 'Informe o nome do doador.')
        if not cleaned.get('email', '').strip() and not cleaned.get('telefone', '').strip():
            self.add_error('email', 'Informe o e-mail ou o telefone do doador.')
        return cleaned


class DoadorInlineForm(forms.ModelForm):
    class Meta:
        model = Doador
        fields = ['tipo', 'nome', 'documento', 'email', 'telefone', 'voluntario']
        labels = {
            'tipo': 'Tipo de doador',
            'nome': 'Nome completo ou razão social',
            'documento': 'CPF ou CNPJ',
            'email': 'E-mail',
            'telefone': 'Telefone',
            'voluntario': 'Voluntário relacionado',
        }
        help_texts = {
            'tipo': 'Escolha pessoa física ou jurídica.',
            'nome': 'Informe o nome que aparecerá no histórico da doação.',
            'email': 'Informe pelo menos um contato: e-mail ou telefone.',
            'telefone': 'Opcional quando houver um e-mail informado.',
            'voluntario': 'Opcional. Busque por nome ou e-mail para preencher o contato com os dados cadastrados.',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Maria da Silva ou Empresa Exemplo Ltda.',
            }),
            'documento': forms.TextInput(attrs={
                'class': 'form-control documento-input',
                'placeholder': 'CPF: 000.000.000-00 ou CNPJ: 00.000.000/0000-00',
                'inputmode': 'numeric',
                'maxlength': '18',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control email-input',
                'placeholder': 'Ex.: contato@exemplo.com',
                'autocomplete': 'email',
                'inputmode': 'email',
                'maxlength': '254',
            }),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control telefone-input',
                'placeholder': 'Ex.: (11) 99999-9999',
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'maxlength': '15',
            }),
            'voluntario': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].choices = [
            ('', 'Selecione o tipo de doador'),
            *Doador.TIPO_CHOICES,
        ]
        self.fields['documento'].widget.attrs['maxlength'] = '18'
        self.fields['telefone'].widget.attrs['maxlength'] = '15'
        self.fields['voluntario'].queryset = (
            self.fields['voluntario'].queryset
            .filter(doador__isnull=True)
            .select_related('usuario')
            .order_by('nome')
        )
        self.fields['voluntario'].required = False
        self.fields['voluntario'].empty_label = 'Não vincular a voluntário'
        self.fields['voluntario'].label_from_instance = (
            lambda voluntario: f'{voluntario.nome} - {voluntario.email}'
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('email'):
            cleaned['email'] = cleaned['email'].strip().lower()
        if cleaned.get('telefone'):
            cleaned['telefone'] = cleaned['telefone'].strip()
        if not cleaned.get('nome', '').strip():
            self.add_error('nome', 'Informe o nome do doador.')
        if not cleaned.get('email', '').strip() and not cleaned.get('telefone', '').strip():
            self.add_error('email', 'Informe o e-mail ou o telefone do doador.')
        return cleaned


class DoacaoForm(forms.ModelForm):
    class Meta:
        model = Doacao
        fields = [
            'tipo', 'doador', 'anonima', 'data_recebimento', 'status',
            'finalidade', 'descricao_finalidade', 'praia', 'acao',
            'observacoes', 'referencia_comprovante',
        ]
        labels = {
            'tipo': 'Tipo de doação',
            'doador': 'Doador relacionado',
            'anonima': 'Doação anônima',
            'data_recebimento': 'Data de recebimento',
            'status': 'Situação',
            'finalidade': 'Finalidade',
            'descricao_finalidade': 'Descrição da finalidade específica',
            'praia': 'Praia beneficiada',
            'acao': 'Ação ou mutirão',
            'observacoes': 'Observações',
            'referencia_comprovante': 'Referência do comprovante',
        }
        help_texts = {
            'tipo': 'Escolha se a doação recebida é financeira ou de materiais.',
            'doador': 'Selecione um doador cadastrado ou marque a opção anônima.',
            'anonima': 'Use quando não for possível ou permitido identificar o doador.',
            'data_recebimento': 'Informe a data em que a doação foi recebida.',
            'status': 'A situação pode ser atualizada depois no controle de doações.',
            'finalidade': 'Indique como a doação será utilizada.',
            'descricao_finalidade': 'Obrigatória quando a finalidade for específica.',
            'praia': 'Opcional. Busque pelo nome da praia ou cidade.',
            'acao': 'Opcional. Busque pelo tipo, praia ou data da ação.',
            'observacoes': 'Registre informações adicionais importantes para o acompanhamento.',
            'referencia_comprovante': 'Opcional. Informe um número, nome de arquivo ou referência.',
        }
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'doador': forms.Select(attrs={'class': 'form-control'}),
            'anonima': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'data_recebimento': forms.DateInput(
                format='%d/%m/%Y',
                attrs={
                    'class': 'form-control data-doacao-input',
                    'type': 'text',
                    'placeholder': 'dd/mm/aaaa',
                    'inputmode': 'numeric',
                    'maxlength': '10',
                },
            ),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'finalidade': forms.Select(attrs={'class': 'form-control'}),
            'descricao_finalidade': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: compra de materiais para a ação de limpeza',
            }),
            'praia': forms.Select(attrs={'class': 'form-control'}),
            'acao': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descreva detalhes que ajudem a identificar ou acompanhar esta doação.',
            }),
            'referencia_comprovante': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: comprovante PIX de 11/10/2026',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_recebimento'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']
        self.fields['tipo'].choices = [('', 'Selecione o tipo de doação'), *Doacao.TIPO_CHOICES]
        self.fields['status'].choices = [('', 'Selecione a situação'), *Doacao.STATUS_CHOICES]
        self.fields['finalidade'].choices = [('', 'Selecione a finalidade'), *Doacao.FINALIDADE_CHOICES]
        doadores_ativos = Doador.objects.filter(ativo=True)
        if self.instance and self.instance.doador_id:
            doadores_ativos = Doador.objects.filter(
                Q(ativo=True) | Q(pk=self.instance.doador_id),
            )
        self.fields['doador'].queryset = doadores_ativos.order_by('nome')
        self.fields['doador'].empty_label = 'Selecione um doador'
        self.fields['praia'].queryset = Praia.objects.filter(praia_ativa='ATIVA').order_by('nome')
        self.fields['praia'].empty_label = 'Sem praia específica'
        self.fields['acao'].queryset = Acao.objects.select_related('praia').order_by('-data')
        self.fields['acao'].empty_label = 'Sem ação específica'

    def clean(self):
        cleaned = super().clean()
        anonima = cleaned.get('anonima')
        doador = cleaned.get('doador')
        if anonima:
            self.fields['doador'].disabled = True
            cleaned['doador'] = None
        elif not doador:
            self.add_error('doador', 'Informe o doador ou marque a doação como anônima.')
        if cleaned.get('data_recebimento') and cleaned['data_recebimento'] > timezone.localdate():
            self.add_error('data_recebimento', 'A data de recebimento não pode ser futura.')
        return cleaned


class DoacaoFinanceiraForm(forms.ModelForm):
    class Meta:
        model = DoacaoFinanceira
        fields = ['valor', 'forma_recebimento']
        labels = {
            'valor': 'Valor recebido',
            'forma_recebimento': 'Forma de recebimento',
        }
        help_texts = {
            'valor': 'Informe o valor em reais. Deve ser maior que zero.',
            'forma_recebimento': 'Selecione como o valor foi recebido.',
        }
        widgets = {
            'valor': forms.TextInput(attrs={
                'class': 'form-control moeda-input',
                'inputmode': 'decimal',
                'placeholder': '0,00',
            }),
            'forma_recebimento': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['forma_recebimento'].choices = [
            ('', 'Selecione a forma de recebimento'),
            *DoacaoFinanceira.FORMA_RECEBIMENTO_CHOICES,
        ]


class ItemDoacaoMaterialForm(forms.ModelForm):
    class Meta:
        model = ItemDoacaoMaterial
        fields = ['material', 'nome', 'categoria', 'quantidade', 'condicao', 'observacoes']
        labels = {
            'material': 'Material do estoque',
            'nome': 'Nome do material',
            'categoria': 'Categoria',
            'quantidade': 'Quantidade',
            'condicao': 'Condição',
            'observacoes': 'Observações do material',
        }
        help_texts = {
            'material': 'Selecione o material correspondente para integrar a entrada ao estoque.',
            'quantidade': 'Use um valor maior que zero. Para confirmar a doação, informe uma quantidade inteira.',
            'observacoes': 'Opcional. Registre detalhes sobre o material recebido.',
        }
        widgets = {
            'material': forms.Select(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: saco de lixo reforçado',
            }),
            'categoria': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: limpeza, alimentação ou escritório',
            }),
            'quantidade': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Ex.: 10',
            }),
            'condicao': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Detalhes opcionais sobre o estado ou uso do material.',
            }),
        }

    def __init__(self, *args, estoque_bloqueado=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.order_by('nome')
        self.fields['material'].empty_label = 'Selecione o material do estoque'
        self.fields['material'].required = False
        if estoque_bloqueado:
            for field in self.fields.values():
                field.disabled = True
        self.fields['condicao'].choices = [
            ('', 'Selecione a condição'),
            *ItemDoacaoMaterial.CONDICAO_CHOICES,
        ]

    def save(self, commit=True):
        if self.cleaned_data.get('material'):
            self.instance.unidade = self.cleaned_data['material'].get_unidade_display()
        return super().save(commit=commit)


class ItemDoacaoMaterialFormSetBase(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        self.estoque_bloqueado = bool(
            instance
            and instance.pk
            and instance.status == Doacao.CONFIRMADA
            and instance.movimentacoes_estoque.exists()
        )
        kwargs.setdefault('form_kwargs', {})['estoque_bloqueado'] = self.estoque_bloqueado
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.instance.status != Doacao.CONFIRMADA:
            return

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if (
                self.instance.pk
                and self.instance.status == Doacao.CONFIRMADA
                and self.estoque_bloqueado
                and form.cleaned_data.get('DELETE')
            ):
                form.add_error(None, 'Itens de uma doação já lançada no estoque não podem ser removidos.')
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            if not form.cleaned_data:
                continue
            if (
                self.instance.pk
                and self.instance.status == Doacao.CONFIRMADA
                and self.estoque_bloqueado
                and not form.has_changed()
            ):
                continue
            material = form.cleaned_data.get('material')
            quantidade = form.cleaned_data.get('quantidade')
            condicao = form.cleaned_data.get('condicao')
            if not material:
                form.add_error('material', 'Selecione o material do estoque antes de confirmar.')
            if quantidade is not None and quantidade != quantidade.to_integral_value():
                form.add_error(
                    'quantidade',
                    'A quantidade precisa ser inteira para movimentar o estoque.',
                )
            if condicao == ItemDoacaoMaterial.CONDICAO_DANIFICADO:
                form.add_error(
                    'condicao',
                    'Materiais danificados não podem ser adicionados ao estoque.',
                )


ItemDoacaoMaterialFormSet = inlineformset_factory(
    Doacao,
    ItemDoacaoMaterial,
    form=ItemDoacaoMaterialForm,
    formset=ItemDoacaoMaterialFormSetBase,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
