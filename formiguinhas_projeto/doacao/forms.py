import uuid

from django import forms
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone

from acao.models import Acao
from auditoria.services import registrar_evento
from estoque.forms import MaterialCategoriaSelect
from estoque.models import Material
from praia.models import Praia

from .models import Doador, Doacao, DoacaoFinanceira, ItemDoacaoMaterial


class MaterialDoacaoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.nome} — {obj.categoria} ({obj.get_unidade_display()})'


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
    acao = forms.ChoiceField(
        required=False,
        label='Ação ou mutirão',
        help_text='Opcional. Busque pelo tipo, praia ou data da ação.',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Doacao
        fields = [
            'tipo', 'doador', 'anonima', 'data_recebimento', 'status',
            'finalidade', 'descricao_finalidade', 'praia',
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
        opcoes_acao = [('', 'Sem ação específica')]
        try:
            from acao.mongo_services import consultar_acoes_mongo
            docs, _ = consultar_acoes_mongo(por_pagina=100)
            for d in docs:
                p_nome = (d.get('praia') or {}).get('nome', '')
                t = d.get('tipo', '')
                dt = d.get('data', '')
                opcoes_acao.append((str(d.get('id_sql')), f'{t} - {p_nome} ({dt})'.strip(' -')))
        except Exception:
            pass
        if len(opcoes_acao) <= 1:
            try:
                for a in Acao.objects.select_related('praia').order_by('-data')[:50]:
                    opcoes_acao.append((str(a.pk), str(a)))
            except Exception:
                pass
        self.fields['acao'].choices = opcoes_acao
        if self.instance and self.instance.acao_id:
            self.initial['acao'] = str(self.instance.acao_id)

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



    def save(self, commit=True):
        instance = super().save(commit=False)
        acao_val = self.cleaned_data.get('acao')
        instance.acao_id = int(acao_val) if acao_val else None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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
    material = MaterialDoacaoChoiceField(
        queryset=Material.objects.none(),
        required=False,
        widget=MaterialCategoriaSelect(attrs={'class': 'material-select-real'}),
    )
    categoria = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Pesquise ou digite uma nova categoria',
            'autocomplete': 'off',
            'role': 'combobox',
            'aria-autocomplete': 'list',
            'aria-expanded': 'false',
            'aria-haspopup': 'listbox',
        }),
    )
    unidade_nova = forms.ChoiceField(
        label='Unidade do novo material',
        required=False,
        choices=[('', 'Selecione a unidade')],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = ItemDoacaoMaterial
        fields = ['material', 'nome', 'categoria', 'quantidade', 'condicao', 'observacoes']
        labels = {
            'material': 'Material existente',
            'nome': 'Material',
            'categoria': 'Categoria',
            'quantidade': 'Quantidade',
            'condicao': 'Condição',
            'observacoes': 'Observações do material',
        }
        help_texts = {
            'material': 'Pesquise e selecione um material existente ou cadastre um novo pelo nome.',
            'categoria': 'Pesquise uma categoria existente ou digite uma nova para o material.',
            'quantidade': 'Use um valor maior que zero. Para confirmar a doação, informe uma quantidade inteira.',
            'observacoes': 'Opcional. Registre detalhes sobre o material recebido.',
        }
        widgets = {
            'material': MaterialCategoriaSelect(attrs={'class': 'form-control'}),
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: saco de lixo reforçado',
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
        materiais = Material.objects.order_by('nome')
        self.fields['material'].queryset = materiais
        self.fields['material'].widget.categorias_por_material = {}
        self.fields['material'].widget.nomes_por_material = {}
        self.fields['material'].widget.unidades_por_material = {}
        for material in materiais:
            material_id = str(material.pk)
            self.fields['material'].widget.categorias_por_material[material_id] = material.categoria
            self.fields['material'].widget.nomes_por_material[material_id] = material.nome
            self.fields['material'].widget.unidades_por_material[material_id] = material.unidade
        self.fields['material'].empty_label = 'Selecione o material do estoque'
        self.fields['material'].required = False
        self.fields['unidade_nova'].choices = [
            ('', 'Selecione a unidade'),
            *Material.UNIDADE_CHOICES,
        ]
        self.fields['nome'].widget.attrs.update({
            'class': 'form-control material-donation-search',
            'placeholder': 'Pesquise um material ou digite um nome novo',
            'autocomplete': 'off',
            'role': 'combobox',
            'aria-autocomplete': 'list',
            'aria-expanded': 'false',
            'aria-controls': f'{self["nome"].auto_id}-opcoes',
        })
        self.categorias_existentes = {}
        for categoria in Material.objects.values_list('categoria', flat=True):
            normalizada = ' '.join(categoria.split())
            if normalizada:
                self.categorias_existentes.setdefault(normalizada.casefold(), normalizada)
        if estoque_bloqueado:
            for field in self.fields.values():
                field.disabled = True
        self.fields['condicao'].choices = [
            ('', 'Selecione a condição'),
            *ItemDoacaoMaterial.CONDICAO_CHOICES,
        ]

    def clean(self):
        cleaned = super().clean()
        material = cleaned.get('material')
        if material:
            cleaned['categoria'] = material.categoria
        else:
            nome = ' '.join((cleaned.get('nome') or '').split())
            cleaned['nome'] = nome
            categoria = ' '.join((cleaned.get('categoria') or '').split())
            cleaned['categoria'] = self.categorias_existentes.get(
                categoria.casefold(), categoria
            )
            if nome:
                if len(nome) > 100:
                    self.add_error('nome', 'O nome de um novo material deve ter até 100 caracteres.')
                if len(cleaned['categoria']) > 50:
                    self.add_error(
                        'categoria',
                        'A categoria de um novo material deve ter até 50 caracteres.',
                    )
                if Material.objects.filter(nome__iexact=nome).exists():
                    self.add_error(
                        'material',
                        'Este material já existe. Selecione-o na lista de resultados.',
                    )
                if not cleaned.get('unidade_nova'):
                    self.add_error(
                        'unidade_nova',
                        'Informe a unidade do novo material para cadastrá-lo no estoque.',
                    )
        return cleaned

    def save(self, commit=True):
        material = self.cleaned_data.get('material')
        if material:
            self.instance.unidade = material.get_unidade_display()
            self.instance.categoria = material.categoria
        else:
            self.instance.unidade = dict(Material.UNIDADE_CHOICES).get(
                self.cleaned_data.get('unidade_nova'), ''
            )
        return super().save(commit=commit)


class ItemDoacaoMaterialFormSetBase(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        self.usuario = kwargs.pop('usuario', None)
        self.estoque_bloqueado = bool(
            instance
            and instance.pk
            and instance.status == Doacao.CONFIRMADA
            and instance.movimentacoes_estoque.exists()
        )
        kwargs.setdefault('form_kwargs', {})['estoque_bloqueado'] = self.estoque_bloqueado
        super().__init__(*args, **kwargs)

    def _vincular_material_novo(self, form, commit):
        if form.cleaned_data.get('material') is None:
            usuario = self.usuario
            material = Material(
                nome=form.cleaned_data['nome'],
                codigo=f"DOACAO-{uuid.uuid4().hex.upper()}",
                categoria=form.cleaned_data['categoria'],
                quantidade_inicial=0,
                estoque_minimo=0,
                unidade=form.cleaned_data['unidade_nova'],
                cadastrado_por=usuario,
                cadastrado_por_nome=(
                    usuario.id_voluntario.nome if usuario else ''
                ),
            )
            material.full_clean()
            if commit:
                material.save()
            form.cleaned_data['material'] = material
            form.instance.material = material
            if usuario and commit:
                registrar_evento(
                    entidade='MATERIAL',
                    instancia=material,
                    acao='CRIACAO',
                    usuario=usuario,
                    resumo=f'Material "{material.nome}" cadastrado com uma doação.',
                )

    def save_new(self, form, commit=True):
        self._vincular_material_novo(form, commit)
        return super().save_new(form, commit)

    def save_existing(self, form, instance, commit=True):
        self._vincular_material_novo(form, commit)
        return super().save_existing(form, instance, commit=commit)

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
            if not material and not form.cleaned_data.get('nome'):
                form.add_error('nome', 'Selecione um material existente ou informe o nome de um novo.')
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
