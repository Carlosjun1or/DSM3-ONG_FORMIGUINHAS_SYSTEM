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
