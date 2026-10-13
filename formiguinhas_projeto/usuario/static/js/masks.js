document.addEventListener('DOMContentLoaded', function () {
    var scrollStorageKey = 'system-scroll-position';

    function salvarPosicaoDaPagina() {
        try {
            sessionStorage.setItem(scrollStorageKey, JSON.stringify({
                position: window.scrollY,
                source: window.location.pathname,
            }));
        } catch (error) {
            // A posição é apenas um aprimoramento; não deve impedir o envio.
        }
    }

    function restaurarPosicaoDaPagina() {
        try {
            var savedScrollData = sessionStorage.getItem(scrollStorageKey);
            if (savedScrollData === null) return;

            var savedScroll = JSON.parse(savedScrollData);
            var currentSource = window.location.pathname;
            if (
                !savedScroll
                || typeof savedScroll.position !== 'number'
                || savedScroll.source !== currentSource
            ) {
                sessionStorage.removeItem(scrollStorageKey);
                return;
            }

            window.setTimeout(function () {
                window.scrollTo(0, savedScroll.position);
                sessionStorage.removeItem(scrollStorageKey);
            }, 0);
        } catch (error) {
            // A posição é apenas um aprimoramento; não deve impedir a navegação.
        }
    }

    document.addEventListener('submit', salvarPosicaoDaPagina, true);
    document.addEventListener('change', function (event) {
        if (event.target.closest('form')) salvarPosicaoDaPagina();
    }, true);
    document.addEventListener('click', function (event) {
        if (event.target.closest('form button[type="submit"], form input[type="submit"]')) {
            salvarPosicaoDaPagina();
        }
    }, true);

    window.addEventListener('beforeunload', salvarPosicaoDaPagina);
    window.addEventListener('pageshow', restaurarPosicaoDaPagina);
    restaurarPosicaoDaPagina();

    document.querySelectorAll('.telefone-input').forEach(function (input) {
        input.addEventListener('input', function () {
            var digits = input.value.replace(/\D/g, '').slice(0, 11);

            if (digits.length <= 10) {
                input.value = digits
                    .replace(/^(\d{2})(\d)/, '($1) $2')
                    .replace(/(\d{4})(\d)/, '$1-$2');
                return;
            }

            input.value = digits
                .replace(/^(\d{2})(\d)/, '($1) $2')
                .replace(/(\d{5})(\d)/, '$1-$2');
        });

        input.dispatchEvent(new Event('input'));
    });

    document.querySelectorAll('.cep-input').forEach(function (input) {
        var ultimaConsulta = '';
        var endereco = document.getElementById('id_endereco');
        var bairro = document.getElementById('id_bairro');
        var cidade = document.getElementById('id_cidade');
        var estado = document.getElementById('id_estado');
        var status = document.getElementById('cep-status');

        function formatarCep() {
            var digits = input.value.replace(/\D/g, '').slice(0, 8);
            input.value = digits.replace(/^(\d{5})(\d)/, '$1-$2');
            return digits;
        }

        function preencherEndereco() {
            var digits = formatarCep();
            if (digits.length !== 8 || digits === ultimaConsulta) return;

            ultimaConsulta = digits;
            if (status) status.textContent = 'Buscando endereço...';
            fetch('https://viacep.com.br/ws/' + digits + '/json/')
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('Falha na consulta do CEP.');
                    }
                    return response.json();
                })
                .then(function (data) {
                    if (data.erro) {
                        throw new Error('CEP não encontrado.');
                    }

                    if (endereco && data.logradouro) endereco.value = data.logradouro;
                    if (bairro && data.bairro) bairro.value = data.bairro;
                    if (cidade && data.localidade) cidade.value = data.localidade;
                    if (estado && data.uf) estado.value = data.uf;
                    if (status) status.textContent = 'Endereço preenchido. Confira os dados.';
                })
                .catch(function () {
                    ultimaConsulta = '';
                    if (status) status.textContent = 'CEP não encontrado. Preencha o endereço manualmente.';
                });
        }

        input.addEventListener('input', preencherEndereco);
        input.addEventListener('blur', preencherEndereco);
        formatarCep();
    });

    document.querySelectorAll('.estado-input').forEach(function (input) {
        input.addEventListener('input', function () {
            input.value = input.value.replace(/[^a-zA-Z]/g, '').slice(0, 2).toUpperCase();
        });
    });

    document.querySelectorAll('.data-nascimento-input').forEach(function (input) {
        if (/^\d{4}-\d{2}-\d{2}$/.test(input.value)) {
            var parts = input.value.split('-');
            input.value = parts[2] + '/' + parts[1] + '/' + parts[0];
        }

        input.addEventListener('input', function () {
            var digits = input.value.replace(/\D/g, '').slice(0, 8);
            input.value = digits
                .replace(/^(\d{2})(\d)/, '$1/$2')
                .replace(/^(\d{2}\/\d{2})(\d)/, '$1/$2');
        });

        input.form.addEventListener('submit', function () {
            var dateParts = input.value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
            if (dateParts) {
                input.value = dateParts[3] + '-' + dateParts[2] + '-' + dateParts[1];
            }
        });
    });

    document.querySelectorAll('.acao-data-input').forEach(function (input) {
        function aplicarMascaraData() {
            var digits = input.value.replace(/\D/g, '').slice(0, 8);
            input.value = digits
                .replace(/^(\d{2})(\d)/, '$1/$2')
                .replace(/^(\d{2}\/\d{2})(\d)/, '$1/$2');
        }

        if (/^\d{4}-\d{2}-\d{2}$/.test(input.value)) {
            var parts = input.value.split('-');
            input.value = parts[2] + '/' + parts[1] + '/' + parts[0];
        }

        input.addEventListener('input', aplicarMascaraData);
        aplicarMascaraData();

        if (input.form) input.form.addEventListener('submit', function () {
            var dateParts = input.value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
            if (dateParts) {
                input.value = dateParts[3] + '-' + dateParts[2] + '-' + dateParts[1];
            }
        });
    });

    document.querySelectorAll('.acao-horario-input').forEach(function (input) {
        function aplicarMascaraHorario() {
            var digits = input.value.replace(/\D/g, '').slice(0, 4);
            input.value = digits.replace(/^(\d{2})(\d)/, '$1:$2');
        }

        input.addEventListener('input', aplicarMascaraHorario);
        input.addEventListener('change', aplicarMascaraHorario);
        aplicarMascaraHorario();
    });

    document.querySelectorAll('.data-hora-input').forEach(function (input) {
        function formatarDataHora(valor) {
            var digits = valor.replace(/\D/g, '').slice(0, 12);
            var data = digits.slice(0, 8)
                .replace(/^(\d{2})(\d)/, '$1/$2')
                .replace(/^(\d{2}\/\d{2})(\d)/, '$1/$2');
            var horario = digits.slice(8)
                .replace(/^(\d{2})(\d)/, '$1:$2');
            input.value = horario ? data + ' ' + horario : data;
        }

        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(input.value)) {
            var partes = input.value.split(/[-T:]/);
            input.value = partes[2] + '/' + partes[1] + '/' + partes[0]
                + ' ' + partes[3] + ':' + partes[4];
        }

        input.addEventListener('input', function () {
            formatarDataHora(input.value);
        });

        if (input.form) {
            input.form.addEventListener('submit', function () {
                var partes = input.value.match(
                    /^(\d{2})\/(\d{2})\/(\d{4})\s(\d{2}):(\d{2})$/
                );
                if (partes) {
                    input.value = partes[3] + '-' + partes[2] + '-' + partes[1]
                        + 'T' + partes[4] + ':' + partes[5];
                }
            });
        }
    });

    document.querySelectorAll('.email-input').forEach(function (input) {
        input.addEventListener('input', function () {
            input.value = input.value.replace(/\s/g, '').toLowerCase();
        });

        input.addEventListener('blur', function () {
            input.value = input.value.trim().toLowerCase();
        });
    });

    document.querySelectorAll('.phone-cell').forEach(function (cell) {
        var digits = cell.textContent.replace(/\D/g, '');
        if (digits.length === 11) {
            cell.textContent = digits.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3');
        } else if (digits.length === 10) {
            cell.textContent = digits.replace(/^(\d{2})(\d{4})(\d{4})$/, '($1) $2-$3');
        }
    });

    document.querySelectorAll('.searchable-select').forEach(function (wrapper) {
        var search = wrapper.querySelector('.volunteer-search');
        var select = wrapper.querySelector('select');
        if (!search || !select) return;

        var options = Array.from(select.options).slice(1);
        search.addEventListener('input', function () {
            var query = search.value.trim().toLowerCase();
            var firstMatch = null;

            options.forEach(function (option) {
                var matches = !query || option.textContent.toLowerCase().includes(query);
                option.hidden = !matches;
                if (matches && !firstMatch) firstMatch = option;
            });

            if (query && firstMatch) {
                select.value = firstMatch.value;
            } else if (!query) {
                select.value = '';
            }
        });

        select.addEventListener('change', function () {
            var selected = select.options[select.selectedIndex];
            if (selected && selected.value) search.value = selected.textContent;
        });
    });

    document.querySelectorAll('.password-toggle').forEach(function (toggle) {
        var field = toggle.closest('.password-field');
        var input = field && field.querySelector('input');
        if (!input) return;

        toggle.addEventListener('click', function () {
            var isVisible = input.type === 'text';
            input.type = isVisible ? 'password' : 'text';
            toggle.textContent = isVisible ? 'Mostrar' : 'Ocultar';
            toggle.setAttribute('aria-label', isVisible ? 'Mostrar senha' : 'Ocultar senha');
            toggle.setAttribute('aria-pressed', String(!isVisible));
        });
    });
});
