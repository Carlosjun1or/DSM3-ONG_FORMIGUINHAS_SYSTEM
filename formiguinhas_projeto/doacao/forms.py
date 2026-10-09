from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils import timezone

from acao.models import Acao
from praia.models import Praia

from .models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial


class DoadorForm(forms.ModelForm):
    class Meta:
        model = Doador
        fields = ['tipo', 'nome', 'documento', 'email', 'telefone', 'voluntario', 'ativo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'voluntario': forms.Select(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['voluntario'].queryset = (
            self.fields['voluntario'].queryset.select_related('usuario').order_by('nome')
        )
        self.fields['voluntario'].required = False
        self.fields['voluntario'].empty_label = 'Não vincular a voluntário'


class DoadorInlineForm(forms.ModelForm):
    class Meta:
        model = Doador
        fields = ['tipo', 'nome', 'documento', 'email', 'telefone']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'documento': forms.TextInput(attrs={
                'class': 'form-control documento-input',
                'maxlength': '18',
            }),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={
                'class': 'form-control telefone-input',
                'maxlength': '15',
            }),
        }


class DoacaoForm(forms.ModelForm):
    class Meta:
        model = Doacao
        fields = [
            'tipo', 'doador', 'anonima', 'data_recebimento', 'status',
            'finalidade', 'descricao_finalidade', 'praia', 'acao',
            'observacoes', 'referencia_comprovante',
        ]
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
            'descricao_finalidade': forms.TextInput(attrs={'class': 'form-control'}),
            'praia': forms.Select(attrs={'class': 'form-control'}),
            'acao': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'referencia_comprovante': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_recebimento'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']
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
        widgets = {
            'valor': forms.TextInput(attrs={
                'class': 'form-control moeda-input',
                'inputmode': 'decimal',
                'placeholder': '0,00',
            }),
            'forma_recebimento': forms.Select(attrs={'class': 'form-control'}),
        }


class ItemDoacaoMaterialForm(forms.ModelForm):
    class Meta:
        model = ItemDoacaoMaterial
        fields = ['nome', 'categoria', 'quantidade', 'unidade', 'condicao', 'observacoes']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unidade': forms.TextInput(attrs={'class': 'form-control'}),
            'condicao': forms.Select(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


ItemDoacaoMaterialFormSet = inlineformset_factory(
    Doacao,
    ItemDoacaoMaterial,
    form=ItemDoacaoMaterialForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
