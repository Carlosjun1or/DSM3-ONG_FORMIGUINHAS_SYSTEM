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

    function iniciarCategorias() {
        document.querySelectorAll('[data-categoria-combobox]').forEach(function (combobox) {
            var campo = combobox.querySelector('input');
            var lista = combobox.querySelector('[data-categoria-options]');
            if (!campo || !lista) return;

            var opcoes = Array.prototype.slice.call(
                lista.querySelectorAll('.categoria-option[data-value]')
            );
            var nenhuma = lista.querySelector('[data-categoria-empty]');
            var nova = lista.querySelector('[data-categoria-nova]');
            var indiceAtivo = -1;

            function fecharLista() {
                lista.hidden = true;
                combobox.classList.remove('is-open');
                campo.setAttribute('aria-expanded', 'false');
                campo.removeAttribute('aria-activedescendant');
                indiceAtivo = -1;
            }

            function atualizarLista() {
                if (campo.readOnly || campo.disabled) {
                    fecharLista();
                    return;
                }
                var termo = campo.value.trim().toLocaleLowerCase();
                var visiveis = 0;
                var categoriaExata = false;
                opcoes.forEach(function (opcao) {
                    var valor = opcao.dataset.value;
                    var visivel = !termo || valor.toLocaleLowerCase().indexOf(termo) !== -1;
                    opcao.hidden = !visivel;
                    opcao.classList.remove('is-active');
                    opcao.setAttribute('aria-selected', 'false');
                    if (visivel) visiveis += 1;
                    if (termo && valor.toLocaleLowerCase() === termo) categoriaExata = true;
                });
                if (nenhuma) {
                    nenhuma.hidden = visiveis > 0;
                    nenhuma.textContent = termo
                        ? 'Nenhuma categoria encontrada com esse nome.'
                        : 'Ainda não há categorias. Digite um nome para cadastrar a primeira.';
                }
                if (nova) {
                    nova.hidden = !termo || categoriaExata;
                    nova.textContent = 'Usar "' + campo.value.trim() + '" como nova categoria';
                    nova.id = campo.id + '-categoria-nova';
                    nova.setAttribute('aria-selected', 'false');
                }
                lista.hidden = false;
                combobox.classList.add('is-open');
                campo.setAttribute('aria-expanded', 'true');
            }

            function opcoesVisiveis() {
                return Array.prototype.filter.call(
                    lista.querySelectorAll('.categoria-option'),
                    function (opcao) { return !opcao.hidden; }
                );
            }

            function definirAtivo(indice) {
                var visiveis = opcoesVisiveis();
                visiveis.forEach(function (opcao, posicao) {
                    var ativo = posicao === indice;
                    opcao.classList.toggle('is-active', ativo);
                    opcao.setAttribute('aria-selected', ativo ? 'true' : 'false');
                    if (ativo) {
                        campo.setAttribute('aria-activedescendant', opcao.id);
                        opcao.scrollIntoView({ block: 'nearest' });
                    }
                });
                indiceAtivo = indice;
            }

            opcoes.forEach(function (opcao, indice) {
                opcao.id = campo.id + '-categoria-' + indice;
                opcao.addEventListener('mousedown', function (evento) {
                    evento.preventDefault();
                    campo.value = opcao.dataset.value;
                    campo.dispatchEvent(new Event('change', { bubbles: true }));
                    fecharLista();
                });
            });
            if (nova) {
                nova.addEventListener('mousedown', function (evento) {
                    evento.preventDefault();
                    fecharLista();
                });
            }
            campo.addEventListener('focus', atualizarLista);
            campo.addEventListener('input', function () {
                indiceAtivo = -1;
                atualizarLista();
            });
            campo.addEventListener('keydown', function (evento) {
                if (evento.key === 'Escape') {
                    fecharLista();
                } else if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
                    evento.preventDefault();
                    atualizarLista();
                    var visiveis = opcoesVisiveis();
                    if (!visiveis.length) return;
                    var proximo = evento.key === 'ArrowDown'
                        ? (indiceAtivo + 1) % visiveis.length
                        : (indiceAtivo - 1 + visiveis.length) % visiveis.length;
                    definirAtivo(proximo);
                } else if (evento.key === 'Enter' && indiceAtivo >= 0) {
                    evento.preventDefault();
                    var ativo = opcoesVisiveis()[indiceAtivo];
                    if (!ativo) return;
                    if (ativo.dataset.value) {
                        campo.value = ativo.dataset.value;
                        campo.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    fecharLista();
                }
            });
            document.addEventListener('mousedown', function (evento) {
                if (!combobox.contains(evento.target)) fecharLista();
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('form[data-filtro-vivo]').forEach(iniciarFiltroVivo);
        document.querySelectorAll('[data-toast]').forEach(iniciarToast);
        iniciarCategorias();
    });
}());
