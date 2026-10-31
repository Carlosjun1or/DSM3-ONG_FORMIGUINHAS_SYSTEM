/* Loading overlay for explicit data-changing actions. */
(function () {
    'use strict';

    var tela = document.getElementById('carregando');
    if (!tela) return;

    var TEMPO_MINIMO_MS = 900;
    var LIMITE_MS = 20000;
    var FADE_MS = 250;
    var CHAVE_ACAO_PENDENTE = 'formiguinhas:loading-action';
    var PADROES_DOWNLOAD = [/\/exportar/i, /[?&]formato=/i];

    var trava = null;
    var fechando = null;

    function abrir() {
        clearTimeout(fechando);
        clearTimeout(trava);
        tela.hidden = false;
        void tela.offsetWidth;
        tela.classList.add('is-visivel');
        trava = setTimeout(fechar, LIMITE_MS);
    }

    function fechar() {
        clearTimeout(trava);
        trava = null;
        tela.classList.remove('is-visivel');
        clearTimeout(fechando);
        fechando = setTimeout(function () {
            if (!tela.classList.contains('is-visivel')) tela.hidden = true;
        }, FADE_MS);
    }

    function ehDownload(texto) {
        return PADROES_DOWNLOAD.some(function (padrao) { return padrao.test(texto || ''); });
    }

    function lerAcaoPendente() {
        var acao;
        try {
            acao = window.sessionStorage.getItem(CHAVE_ACAO_PENDENTE);
            window.sessionStorage.removeItem(CHAVE_ACAO_PENDENTE);
        } catch (erro) {
            console.warn('Não foi possível recuperar a ação de carregamento.', erro);
            return null;
        }
        if (!acao) return null;
        try {
            acao = JSON.parse(acao);
        } catch (erro) {
            console.warn('A ação de carregamento pendente está inválida.', erro);
            return null;
        }
        if (!acao || Date.now() - acao.criadaEm > LIMITE_MS) return null;
        if (acao.tipo === 'login' && window.location.pathname !== acao.destino) return null;
        return acao;
    }

    function aposCarregar() {
        var restante = Math.max(0, TEMPO_MINIMO_MS - window.performance.now());
        setTimeout(fechar, restante);
    }

    function registrarAcao(tipo, mostrarAgora, destino) {
        try {
            window.sessionStorage.setItem(CHAVE_ACAO_PENDENTE, JSON.stringify({
                criadaEm: Date.now(),
                destino: destino || null,
                origem: window.location.pathname,
                tipo: tipo,
            }));
        } catch (erro) {
            console.warn('Não foi possível registrar a ação de carregamento.', erro);
        }
        if (mostrarAgora !== false) abrir();
    }

    function mostrarDownload() {
        abrir();
        setTimeout(fechar, 4000);
    }

    var acaoPendente = lerAcaoPendente();
    if (acaoPendente) {
        abrir();
        if (document.readyState === 'complete') aposCarregar();
        else window.addEventListener('load', aposCarregar, { once: true });
    }

    // Voltar/avançar do navegador pode restaurar a página do cache com a tela aberta.
    window.addEventListener('pageshow', function (evento) {
        if (evento.persisted) fechar();
    });

    document.addEventListener('click', function (evento) {
        var link = evento.target.closest ? evento.target.closest('a[data-carregando]') : null;
        if (!link || evento.defaultPrevented || evento.button !== 0) return;
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
        if (link.target && link.target !== '_self') return;

        if (link.hasAttribute('data-carregando-download')) {
            mostrarDownload();
            return;
        }
        registrarAcao('navigation');
    });

    function prepararEnvio(formulario, botao) {
        if (!formulario) return;
        if (formulario.hasAttribute('data-sem-carregando')) return;
        if (botao && botao.hasAttribute('data-sem-carregando')) return;
        if (formulario.target && formulario.target !== '_self') return;

        if (botao && botao.hasAttribute('data-carregando-download')) {
            mostrarDownload();
            return;
        }
        if (formulario.method.toLowerCase() !== 'post') return;
        if (botao && botao.name === 'formato') return;
        if (ehDownload(formulario.action || '')) return;

        var login = formulario.hasAttribute('data-carregando-login');
        registrarAcao(
            login ? 'login' : 'post',
            !login,
            login ? formulario.getAttribute('data-carregando-destino') : null
        );
    }

    document.addEventListener('submit', function (evento) {
        if (evento.defaultPrevented) return;
        prepararEnvio(evento.target, evento.submitter);
    });

    var enviarOriginal = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function () {
        prepararEnvio(this, null);
        return enviarOriginal.apply(this, arguments);
    };
}());
