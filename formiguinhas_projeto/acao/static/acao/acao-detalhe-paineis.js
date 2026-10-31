(function () {
    document.querySelectorAll('[data-abrir-painel]').forEach(function (botao) {
        var painel = document.getElementById(botao.dataset.abrirPainel);
        var rotulo = botao.querySelector('span');
        if (!painel || !rotulo) return;

        var textoFechado = rotulo.textContent.trim();
        var textoAberto = botao.dataset.textoAberto || 'Fechar';
        botao.setAttribute('aria-controls', painel.id);

        function atualizar(aberto) {
            painel.hidden = !aberto;
            botao.setAttribute('aria-expanded', aberto ? 'true' : 'false');
            rotulo.textContent = aberto ? textoAberto : textoFechado;
        }

        atualizar(!painel.hidden);
        botao.addEventListener('click', function () {
            var abrir = painel.hidden;
            atualizar(abrir);
            if (abrir) {
                var campo = painel.querySelector('input:not([type="hidden"]), select, textarea');
                if (campo) campo.focus({ preventScroll: true });
            }
        });
    });
}());