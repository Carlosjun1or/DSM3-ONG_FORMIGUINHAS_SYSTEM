/* Comportamentos do módulo de estoque: filtros em tempo real e aviso de sucesso. */
(function () {
    'use strict';

    // ---- Filtros em tempo real -------------------------------------------------
    var ATRASO_DIGITACAO = 300;

    function urlDoFormulario(form) {
        var parametros = new URLSearchParams();
        new FormData(form).forEach(function (valor, chave) {
            if (String(valor).trim() !== '') {
                parametros.append(chave, valor);
            }
        });
        var consulta = parametros.toString();
        return window.location.pathname + (consulta ? '?' + consulta : '');
    }

    function iniciarFiltroVivo(form) {
        var temporizador = null;
        var controlador = null;

        function atualizar() {
            var url = urlDoFormulario(form);
            if (controlador) {
                controlador.abort();
            }
            controlador = new AbortController();
            form.classList.add('filtro-carregando');

            fetch(url, {
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: controlador.signal,
            })
                .then(function (resposta) {
                    if (!resposta.ok || resposta.redirected) {
                        // Sessão expirada ou erro: recarrega a página normalmente.
                        window.location.href = url;
                        return null;
                    }
                    return resposta.text();
                })
                .then(function (html) {
                    if (html === null) {
                        return;
                    }
                    var novo = new DOMParser().parseFromString(html, 'text/html');
                    document.querySelectorAll('[data-live]').forEach(function (atual) {
                        var substituto = novo.querySelector('[data-live="' + atual.dataset.live + '"]');
                        if (substituto) {
                            atual.replaceWith(substituto);
                        }
                    });
                    window.history.replaceState(null, '', url);
                    form.classList.remove('filtro-carregando');
                })
                .catch(function (erro) {
                    if (erro.name !== 'AbortError') {
                        form.classList.remove('filtro-carregando');
                    }
                });
        }

        form.addEventListener('input', function (evento) {
            var campo = evento.target;
            if (campo.tagName === 'SELECT' || campo.type === 'date') {
                return; // tratados em "change"
            }
            clearTimeout(temporizador);
            temporizador = setTimeout(atualizar, ATRASO_DIGITACAO);
        });
        form.addEventListener('change', function () {
            clearTimeout(temporizador);
            atualizar();
        });
        form.addEventListener('submit', function (evento) {
            evento.preventDefault();
            clearTimeout(temporizador);
            atualizar();
        });
    }

    // ---- Aviso de sucesso (toast) ---------------------------------------------
    function iniciarToast(aviso) {
        aviso.classList.add('toast-estoque');
        aviso.setAttribute('tabindex', '0');
        var fechar = function () {
            aviso.classList.add('toast-saindo');
            setTimeout(function () { aviso.remove(); }, 300);
        };
        aviso.addEventListener('click', fechar);
        setTimeout(fechar, 6000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-filtro-vivo]').forEach(iniciarFiltroVivo);
        document.querySelectorAll('[data-toast]').forEach(iniciarToast);
    });
}());
