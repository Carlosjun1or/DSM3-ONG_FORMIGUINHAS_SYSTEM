document.addEventListener('DOMContentLoaded', function () {
    var sidebar = document.querySelector('.sidebar');
    var sidebarToggle = document.querySelector('.sidebar-toggle');
    var sidebarBackdrop = document.querySelector('.sidebar-backdrop');
    var sidebarMedia = window.matchMedia('(max-width: 900px)');

    function setSidebarOpen(isOpen, returnFocus) {
        if (!sidebar || !sidebarToggle || !sidebarBackdrop) return;

        document.body.classList.toggle('sidebar-open', isOpen);
        sidebarToggle.setAttribute('aria-expanded', String(isOpen));
        sidebarToggle.setAttribute('aria-label', isOpen ? 'Fechar menu' : 'Abrir menu');
        sidebar.setAttribute('aria-hidden', String(sidebarMedia.matches && !isOpen));
        sidebar.inert = sidebarMedia.matches && !isOpen;
        sidebarBackdrop.setAttribute('aria-hidden', String(!isOpen));
        sidebarBackdrop.inert = !isOpen;

        if (isOpen) {
            var firstLink = sidebar.querySelector('a[href]');
            if (firstLink) firstLink.focus();
        } else if (returnFocus) {
            sidebarToggle.focus();
        }
    }

    if (sidebar && sidebarToggle && sidebarBackdrop) {
        setSidebarOpen(false, false);

        sidebarToggle.addEventListener('click', function () {
            setSidebarOpen(sidebarToggle.getAttribute('aria-expanded') !== 'true', false);
        });

        sidebarBackdrop.addEventListener('click', function () {
            setSidebarOpen(false, true);
        });

        sidebar.addEventListener('click', function (event) {
            if (event.target.closest('a[href]')) setSidebarOpen(false, false);
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && sidebarToggle.getAttribute('aria-expanded') === 'true') {
                setSidebarOpen(false, true);
            }
        });

        sidebarMedia.addEventListener('change', function (event) {
            setSidebarOpen(false, false);
            sidebar.setAttribute('aria-hidden', String(event.matches));
            sidebar.inert = event.matches;
        });
    }

    var sidebarResizeHandle = document.querySelector('.sidebar-resize-handle');
    var sidebarWidthStorageKey = 'system-sidebar-width';
    var sidebarDefaultWidth = 300;
    var sidebarMinWidth = 220;
    var sidebarMaxWidth = 480;
    var resizingSidebar = false;

    function getSidebarWidthBounds() {
        return {
            min: sidebarMinWidth,
            max: Math.max(sidebarMinWidth, Math.min(
                sidebarMaxWidth,
                window.innerWidth - 360
            )),
        };
    }

    function setSidebarWidth(width, persist) {
        if (!sidebar || !sidebarResizeHandle) return;

        var bounds = getSidebarWidthBounds();
        var clampedWidth = Math.round(Math.max(
            bounds.min,
            Math.min(bounds.max, width)
        ));
        sidebar.style.setProperty('--sidebar-width', clampedWidth + 'px');
        sidebarResizeHandle.setAttribute('aria-valuemax', String(bounds.max));
        sidebarResizeHandle.setAttribute('aria-valuenow', String(clampedWidth));
        sidebarResizeHandle.setAttribute(
            'aria-valuetext',
            clampedWidth + ' pixels'
        );

        if (persist) {
            try {
                localStorage.setItem(sidebarWidthStorageKey, String(clampedWidth));
            } catch (error) {
                console.warn('Não foi possível salvar a largura do menu lateral.', error);
            }
        }
    }

    if (sidebar && sidebarResizeHandle) {
        document.addEventListener('keydown', function (event) {
            if (event.key !== 'F5' || !event.ctrlKey) return;

            setSidebarWidth(sidebarDefaultWidth, false);
            try {
                localStorage.removeItem(sidebarWidthStorageKey);
            } catch (error) {
                console.warn('Não foi possível remover a largura salva do menu lateral.', error);
            }
        });

        try {
            var savedSidebarWidth = Number(
                localStorage.getItem(sidebarWidthStorageKey)
            );
            if (Number.isFinite(savedSidebarWidth) && savedSidebarWidth > 0) {
                setSidebarWidth(savedSidebarWidth, false);
            } else {
                setSidebarWidth(300, false);
            }
        } catch (error) {
            setSidebarWidth(300, false);
            console.warn('Não foi possível carregar a largura salva do menu lateral.', error);
        }

        sidebarResizeHandle.addEventListener('pointerdown', function (event) {
            if (sidebarMedia.matches) return;
            event.preventDefault();
            resizingSidebar = true;
            document.body.classList.add('sidebar-resizing');
            sidebarResizeHandle.setPointerCapture(event.pointerId);
            setSidebarWidth(event.clientX, false);
        });

        sidebarResizeHandle.addEventListener('pointermove', function (event) {
            if (resizingSidebar) setSidebarWidth(event.clientX, false);
        });

        function finishSidebarResize(event) {
            if (!resizingSidebar) return;
            resizingSidebar = false;
            document.body.classList.remove('sidebar-resizing');
            if (sidebarResizeHandle.hasPointerCapture(event.pointerId)) {
                sidebarResizeHandle.releasePointerCapture(event.pointerId);
            }
            setSidebarWidth(
                Number(sidebarResizeHandle.getAttribute('aria-valuenow')),
                true
            );
        }

        sidebarResizeHandle.addEventListener('pointerup', finishSidebarResize);
        sidebarResizeHandle.addEventListener('pointercancel', finishSidebarResize);

        function restoreDefaultSidebarWidth() {
            setSidebarWidth(sidebarDefaultWidth, true);
        }

        sidebarResizeHandle.addEventListener('dblclick', function () {
            restoreDefaultSidebarWidth();
            sidebarResizeHandle.focus();
        });

        sidebarResizeHandle.addEventListener('keydown', function (event) {
            var width = Number(
                sidebarResizeHandle.getAttribute('aria-valuenow')
            ) || 300;
            var nextWidth;

            if (event.key === 'ArrowRight') nextWidth = width + 16;
            else if (event.key === 'ArrowLeft') nextWidth = width - 16;
            else if (event.key === 'Home') {
                event.preventDefault();
                restoreDefaultSidebarWidth();
                return;
            }
            else if (event.key === 'End') nextWidth = getSidebarWidthBounds().max;
            else return;

            event.preventDefault();
            setSidebarWidth(nextWidth, true);
        });

        window.addEventListener('resize', function () {
            setSidebarWidth(
                Number(sidebarResizeHandle.getAttribute('aria-valuenow')) || 300,
                false
            );
        });

    }

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

    document.querySelectorAll('.data-doacao-input').forEach(function (input) {
        function aplicarMascaraData() {
            var digits = input.value.replace(/\D/g, '').slice(0, 8);
            input.value = digits
                .replace(/^(\d{2})(\d)/, '$1/$2')
                .replace(/^(\d{2}\/\d{2})(\d)/, '$1/$2');
        }
        if (/^\d{4}-\d{2}-\d{2}$/.test(input.value)) {
            var partes = input.value.split('-');
            input.value = partes[2] + '/' + partes[1] + '/' + partes[0];
        }
        input.addEventListener('input', aplicarMascaraData);
        aplicarMascaraData();
        if (input.form) input.form.addEventListener('submit', function () {
            var partes = input.value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
            if (partes) input.value = partes[3] + '-' + partes[2] + '-' + partes[1];
        });
    });

    document.querySelectorAll('.documento-input').forEach(function (input) {
        function aplicarMascaraDocumento() {
            var digits = input.value.replace(/\D/g, '').slice(0, 14);
            if (digits.length <= 11) {
                input.value = digits
                    .replace(/^(\d{3})(\d)/, '$1.$2')
                    .replace(/^(\d{3}\.\d{3})(\d)/, '$1.$2')
                    .replace(/^(\d{3}\.\d{3}\.\d{3})(\d)/, '$1-$2');
            } else {
                input.value = digits
                    .replace(/^(\d{2})(\d)/, '$1.$2')
                    .replace(/^(\d{2}\.\d{3})(\d)/, '$1.$2')
                    .replace(/^(\d{2}\.\d{3}\.\d{3})(\d)/, '$1/$2')
                    .replace(/^(\d{2}\.\d{3}\.\d{3}\/\d{4})(\d)/, '$1-$2');
            }
        }

        input.addEventListener('input', aplicarMascaraDocumento);
        aplicarMascaraDocumento();
    });

    document.querySelectorAll('.moeda-input').forEach(function (input) {
        input.addEventListener('input', function () {
            var digits = input.value.replace(/\D/g, '');
            if (!digits) {
                input.value = '';
                return;
            }
            input.value = (Number(digits) / 100).toFixed(2).replace('.', ',');
        });
        if (input.form) input.form.addEventListener('submit', function () {
            input.value = input.value.replace(/\./g, '').replace(',', '.');
        });
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

        if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(input.value)) {
            var partes = input.value.split(/[-T: :.]/);
            input.value = partes[2] + '/' + partes[1] + '/' + partes[0]
                + ' ' + partes[3] + ':' + partes[4];
        }

        input.addEventListener('input', function () {
            formatarDataHora(input.value);
        });

        document.querySelectorAll('.relationship-search').forEach(function (search) {
            var select = document.getElementById(search.dataset.target);
            if (!select) return;

            search.addEventListener('input', function () {
                var query = search.value.trim().toLowerCase();
                Array.from(select.options).forEach(function (option) {
                    option.hidden = query !== ''
                        && !option.textContent.toLowerCase().includes(query);
                });
            });
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
            var inicio = input.selectionStart;
            var antes = input.value;
            var depois = antes.replace(/\s/g, '').toLowerCase();
            if (antes === depois) return;

            var removidosAntesDoCursor = antes
                .slice(0, inicio)
                .replace(/\s/g, '').length;
            input.value = depois;
            if (
                input.type !== 'email'
                && typeof input.setSelectionRange === 'function'
            ) {
                input.setSelectionRange(
                    removidosAntesDoCursor,
                    removidosAntesDoCursor,
                );
            }
        });

        input.addEventListener('blur', function () {
            input.value = input.value.replace(/\s/g, '').trim().toLowerCase();
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

    document.querySelectorAll('.document-cell').forEach(function (cell) {
        var digits = cell.textContent.replace(/\D/g, '');
        if (digits.length === 11) {
            cell.textContent = digits
                .replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4');
        } else if (digits.length === 14) {
            cell.textContent = digits
                .replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
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
