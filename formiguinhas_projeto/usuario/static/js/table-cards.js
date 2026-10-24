(() => {
    const actionColumn = /^(ações|opções|gerenciar|operações)$/i;
    const statusColumn = /^(status|situação)$/i;

    function createField(label, cell) {
        const field = document.createElement('div');
        field.className = 'record-table-card-field';

        const heading = document.createElement('span');
        heading.className = 'record-table-card-label';
        heading.textContent = label;
        field.appendChild(heading);

        const value = document.createElement('div');
        value.className = 'record-table-card-value';
        while (cell.firstChild) {
            value.appendChild(cell.firstChild);
        }
        if (!value.childNodes.length) {
            value.textContent = '—';
        }
        field.appendChild(value);
        return field;
    }

    function transformTable(table) {
        if (table.dataset.cardsReady === 'true') {
            return;
        }

        const rows = Array.from(table.tBodies).flatMap((body) => Array.from(body.rows));
        if (!rows.length) {
            return;
        }

        const headerRows = Array.from(table.tHead?.rows || []);
        const headerRow = headerRows.reverse().find((row) => row.cells.length > 0);
        const headers = headerRow
            ? Array.from(headerRow.cells, (cell) => cell.textContent.trim())
            : [];
        const list = document.createElement('div');
        list.className = 'record-table-cards';
        list.setAttribute('role', 'list');

        rows.forEach((row) => {
            const cells = Array.from(row.cells);
            if (!cells.length) {
                return;
            }
            const isExpandableResidue = table.closest('.residue-records-table') !== null;
            const residueDetails = isExpandableResidue
                ? [
                    ['Observação completa', cells[5]],
                    ['Destinação', cells[3]],
                    ['Histórico', cells[4]],
                ]
                : [];

            const card = document.createElement('article');
            card.className = 'record-table-card';
            card.setAttribute('role', 'listitem');

            const identity = document.createElement('div');
            identity.className = 'record-table-card-identity';
            const identityLabel = document.createElement('span');
            identityLabel.className = 'record-table-card-label';
            identityLabel.textContent = headers[0] || 'Registro';
            identity.appendChild(identityLabel);

            const identityValue = document.createElement('div');
            identityValue.className = 'record-table-card-value record-table-card-title';
            if (isExpandableResidue && cells[0].querySelector('.table-secondary')) {
                const category = cells[0].querySelector('.table-secondary').cloneNode(true);
                identityValue.appendChild(cells[0].querySelector('strong').cloneNode(true));
                identityValue.appendChild(category);
            }
            while (cells[0].firstChild) {
                if (isExpandableResidue && cells[0].querySelector('.table-secondary')) {
                    cells[0].querySelector('.table-secondary').remove();
                }
                identityValue.appendChild(cells[0].firstChild);
            }
            if (!identityValue.childNodes.length) {
                identityValue.textContent = '—';
            }
            identity.appendChild(identityValue);

            const fields = document.createElement('div');
            fields.className = 'record-table-card-fields';
            const actions = document.createElement('div');
            actions.className = 'record-table-card-actions';

            cells.slice(1).forEach((cell, offset) => {
                const index = offset + 1;
                const label = headers[index] || `Informação ${index + 1}`;
                const hasActions = cell.querySelector('a.btn, button, input[type="submit"]');
                if (
                    actionColumn.test(label)
                    || cell.classList.contains('table-actions')
                    || (/^ação$/i.test(label) && hasActions)
                ) {
                    while (cell.firstChild) {
                        actions.appendChild(cell.firstChild);
                    }
                    return;
                }

                const field = createField(label, cell);
                if (statusColumn.test(label)) {
                    field.classList.add('record-table-card-status');
                    identity.appendChild(field);
                } else {
                    if (cell.querySelector('.audit-action') || (/^ação$/i.test(label) && !hasActions)) {
                        field.classList.add('record-table-card-event');
                    }
                    fields.appendChild(field);
                }
            });

            card.append(identity, fields);
            if (residueDetails.length) {
                const details = document.createElement('div');
                details.className = 'record-table-card-details';
                details.setAttribute('aria-hidden', 'true');

                residueDetails.forEach(([label, cell]) => {
                    const detail = document.createElement('div');
                    detail.className = 'record-table-card-detail';

                    const heading = document.createElement('span');
                    heading.className = 'record-table-card-label';
                    heading.textContent = label;

                    const value = document.createElement('div');
                    value.className = 'record-table-card-detail-value';
                    if (cell) {
                        value.appendChild(cell.cloneNode(true));
                    }
                    if (!value.textContent.trim()) {
                        value.textContent = '—';
                    }

                    detail.append(heading, value);
                    details.appendChild(detail);
                });

                card.appendChild(details);
            }
            if (actions.childNodes.length) {
                card.appendChild(actions);
            }

            if (isExpandableResidue) {
                card.classList.add('record-table-card--expandable');
                const toggle = document.createElement('button');
                toggle.className = 'record-table-card-toggle';
                toggle.type = 'button';
                toggle.setAttribute('aria-expanded', 'false');
                toggle.textContent = 'Expandir';
                toggle.addEventListener('click', (event) => {
                    event.stopPropagation();
                    const expanded = card.classList.toggle('is-expanded');
                    toggle.setAttribute('aria-expanded', String(expanded));
                    toggle.textContent = expanded ? 'Recolher' : 'Expandir';
                    const details = card.querySelector('.record-table-card-details');
                    if (details) {
                        details.setAttribute('aria-hidden', String(!expanded));
                    }
                });
                card.appendChild(toggle);
                card.addEventListener('click', (event) => {
                    if (event.target.closest('a, button, input, select, textarea, summary, label')) {
                        return;
                    }
                    toggle.click();
                });
            }
            list.appendChild(card);
        });

        if (!list.childElementCount) {
            return;
        }

        table.dataset.cardsReady = 'true';
        table.hidden = true;
        const wrapper = table.closest('.table-wrap');
        if (wrapper) {
            wrapper.classList.add('has-record-table-cards');
            if (wrapper.classList.contains('unified-collections-table')) {
                list.classList.add('record-table-cards--limited');
            }
            if (wrapper.classList.contains('residue-records-table')) {
                list.classList.add('record-table-cards--expandable');
            }
        }
        table.insertAdjacentElement('afterend', list);
    }

    document.querySelectorAll('table.data-table').forEach(transformTable);
})();
