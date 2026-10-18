(function () {
    document.querySelectorAll('[data-material-combobox]').forEach(function (combobox) {
        var busca = combobox.querySelector('[data-material-search]');
        var opcoesMaterial = combobox.querySelector('[data-material-options]');
        var material = combobox.querySelector('select');
        if (!busca || !opcoesMaterial || !material) return;

        var opcoes = Array.prototype.filter.call(material.options, function (opcao) {
            return opcao.value;
        });
        var indiceAtivo = -1;

        function fecharOpcoes() {
            opcoesMaterial.hidden = true;
            busca.setAttribute('aria-expanded', 'false');
            indiceAtivo = -1;
        }

        function selecionar(opcao) {
            material.value = opcao.value;
            busca.value = opcao.textContent;
            fecharOpcoes();
            material.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function renderizarOpcoes() {
            var termo = busca.value.trim().toLowerCase();
            var encontradas = opcoes.filter(function (opcao) {
                return opcao.textContent.toLowerCase().indexOf(termo) !== -1;
            });
            opcoesMaterial.innerHTML = '';
            encontradas.forEach(function (opcao, indice) {
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'material-option';
                item.setAttribute('role', 'option');
                item.setAttribute('data-value', opcao.value);
                item.textContent = opcao.textContent;
                item.addEventListener('mousedown', function (evento) {
                    evento.preventDefault();
                    selecionar(opcao);
                });
                item.classList.toggle('is-active', indice === indiceAtivo);
                opcoesMaterial.appendChild(item);
            });
            if (!encontradas.length) {
                var vazio = document.createElement('div');
                vazio.className = 'material-options-empty';
                vazio.textContent = 'Nenhum material encontrado.';
                opcoesMaterial.appendChild(vazio);
            }
            opcoesMaterial.hidden = false;
            busca.setAttribute('aria-expanded', 'true');
            return encontradas;
        }

        busca.value = material.value
            ? material.options[material.selectedIndex].textContent
            : '';
        busca.addEventListener('focus', renderizarOpcoes);
        busca.addEventListener('input', function () {
            indiceAtivo = -1;
            if (material.value) material.value = '';
            renderizarOpcoes();
        });
        busca.addEventListener('keydown', function (evento) {
            var itens = opcoesMaterial.querySelectorAll('.material-option');
            if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
                evento.preventDefault();
                if (!itens.length) return;
                indiceAtivo = evento.key === 'ArrowDown'
                    ? (indiceAtivo + 1) % itens.length
                    : (indiceAtivo - 1 + itens.length) % itens.length;
                Array.prototype.forEach.call(itens, function (item, indice) {
                    item.classList.toggle('is-active', indice === indiceAtivo);
                });
            } else if (evento.key === 'Enter' && indiceAtivo >= 0 && itens[indiceAtivo]) {
                evento.preventDefault();
                selecionar(opcoes.find(function (opcao) {
                    return opcao.value === itens[indiceAtivo].getAttribute('data-value');
                }));
            } else if (evento.key === 'Escape') {
                fecharOpcoes();
            }
        });
        document.addEventListener('click', function (evento) {
            if (!combobox.contains(evento.target)) fecharOpcoes();
        });
    });
}());
