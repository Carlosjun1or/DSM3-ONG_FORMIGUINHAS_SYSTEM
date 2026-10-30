(() => {
    document.querySelectorAll('[data-detail-panel-toggle]').forEach((button) => {
        const panel = document.getElementById(button.dataset.detailPanelToggle);
        const label = button.querySelector('span:last-child');
        const icon = button.querySelector('[aria-hidden="true"]');

        if (!panel || !label) {
            return;
        }

        const closedLabel = label.textContent.trim();
        const openLabel = button.dataset.textoAberto || 'Fechar';

        function setExpanded(expanded) {
            panel.hidden = !expanded;
            button.setAttribute('aria-expanded', String(expanded));
            label.textContent = expanded ? openLabel : closedLabel;
            if (icon) {
                icon.textContent = expanded ? '−' : '+';
            }
        }

        setExpanded(!panel.hidden);
        button.addEventListener('click', () => {
            const expanded = panel.hidden;
            setExpanded(expanded);
            if (expanded) {
                const field = panel.querySelector('input:not([type="hidden"]), select, textarea');
                field?.focus({ preventScroll: true });
            }
        });
    });
})();
