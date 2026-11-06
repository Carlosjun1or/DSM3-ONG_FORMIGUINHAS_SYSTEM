(function () {
    'use strict';

    var seletor = document.getElementById('id_relatorio');
    var camposPorRelatorio = {
        geral: ['start', 'end', 'beach'],
        indicadores: ['period', 'beach'],
        acoes: ['start', 'end', 'beach', 'action', 'action-type'],
        voluntarios: ['start', 'end', 'action-type'],
        presenca: ['start', 'end', 'beach', 'action', 'action-type'],
        residuos: ['start', 'end', 'beach', 'action', 'waste-type'],
        estoque: ['start', 'end'],
        doacoes: ['start', 'end']
    };

    function atualizarFiltros() {
        if (!seletor) {
            return;
        }
        var visiveis = camposPorRelatorio[seletor.value] || camposPorRelatorio.geral;
        document.querySelectorAll('[data-report-filter]').forEach(function (campo) {
            campo.hidden = visiveis.indexOf(campo.getAttribute('data-report-filter')) === -1;
        });
    }

    if (seletor) {
        seletor.addEventListener('change', atualizarFiltros);
        atualizarFiltros();
    }

    var elementoDados = document.getElementById('report-charts');
    if (!elementoDados) {
        return;
    }
    if (!window.Chart) {
        console.error('Chart.js não foi carregado; os dados dos gráficos estão disponíveis nas tabelas.');
        return;
    }

    var graficos = JSON.parse(elementoDados.textContent);
    var paleta = ['#0058b9', '#7657cb', '#f4e01e', '#6b7280'];
    Chart.defaults.font.family = 'Quicksand, Fredoka, sans-serif';
    Chart.defaults.color = '#00306b';

    graficos.forEach(function (grafico) {
        if (!grafico.has_data) {
            return;
        }
        var canvas = document.getElementById(grafico.id);
        if (!canvas) {
            return;
        }

        var datasets = grafico.datasets.map(function (dataset, index) {
            var serie = Object.assign({}, dataset);
            if (grafico.tipo === 'doughnut') {
                serie.backgroundColor = dataset.backgroundColor || grafico.labels.map(function (_, colorIndex) {
                    return paleta[colorIndex % paleta.length];
                });
                serie.borderColor = dataset.borderColor || '#00306b';
                serie.borderWidth = dataset.borderWidth || 2;
            } else if (dataset.type !== 'line') {
                serie.backgroundColor = dataset.backgroundColor || paleta[index % paleta.length];
                serie.borderColor = dataset.borderColor || '#00306b';
                serie.borderWidth = dataset.borderWidth || 2;
            }
            return serie;
        });
        var horizontal = [
            'acoes-por-praia',
            'voluntarios-participacoes',
            'estoque-percentual-minimo',
            'doacoes-financeiro-por-doador'
        ].indexOf(grafico.id) !== -1 || grafico.id.indexOf('residuos-tipo-') === 0;
        var opcoes = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { enabled: true }
            }
        };
        if (grafico.tipo !== 'doughnut') {
            if (horizontal) {
                opcoes.indexAxis = 'y';
                opcoes.scales = {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            color: '#374151',
                            callback: function (valor) {
                                return grafico.id === 'estoque-percentual-minimo' ? valor + '%' : valor;
                            }
                        },
                        grid: { color: '#e5e7eb' }
                    },
                    y: {
                        ticks: { color: '#00306b' },
                        grid: { display: false }
                    }
                };
            } else {
                opcoes.scales = {
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#374151' },
                        grid: { color: '#e5e7eb' }
                    },
                    x: {
                        ticks: { color: '#374151' },
                        grid: { display: false }
                    }
                };
            }
        }
        new Chart(canvas, {
            type: grafico.tipo,
            data: { labels: grafico.labels, datasets: datasets },
            options: opcoes
        });
    });
}());
