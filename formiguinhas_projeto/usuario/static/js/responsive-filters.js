document.addEventListener('DOMContentLoaded', function () {
    var mobileViewport = window.matchMedia('(max-width: 720px)');

    document.querySelectorAll('.system-page form.volunteer-filters').forEach(function (form, index) {
        var groups = Array.from(form.querySelectorAll(':scope > .form-group'));
        if (groups.length < 2) return;

        var primaryGroup = groups.find(function (group) {
            return group.querySelector('input[type="search"]');
        }) || groups[0];
        var advancedGroups = groups.filter(function (group) {
            return group !== primaryGroup;
        });
        if (!advancedGroups.length) return;

        var panel = document.createElement('div');
        panel.className = 'responsive-advanced-filters';
        panel.id = 'responsive-filters-panel-' + (index + 1);
        advancedGroups.forEach(function (group) {
            panel.appendChild(group);
        });

        var button = document.createElement('button');
        button.className = 'responsive-advanced-toggle';
        button.type = 'button';
        button.setAttribute('aria-controls', panel.id);

        var label = document.createElement('span');
        button.appendChild(label);

        primaryGroup.classList.add('responsive-primary-filter');
        form.classList.add('responsive-filter-form');
        primaryGroup.after(button);
        button.after(panel);

        var filterActions = form.querySelector(':scope > .filter-actions');
        if (filterActions) filterActions.classList.add('responsive-filter-actions');

        var expanded = !mobileViewport.matches || hasAppliedFilters(panel);

        function hasAppliedFilters(container) {
            var params = new URLSearchParams(window.location.search);
            return Array.from(container.querySelectorAll('input, select, textarea')).some(function (field) {
                return field.name && params.getAll(field.name).some(function (value) {
                    return value !== '';
                });
            });
        }

        function updateExpandedState() {
            label.textContent = expanded ? 'Menos filtros' : 'Mais filtros';
            button.setAttribute('aria-expanded', String(expanded));
            panel.hidden = mobileViewport.matches && !expanded;
        }

        button.addEventListener('click', function () {
            expanded = !expanded;
            updateExpandedState();
            if (expanded) {
                var firstField = panel.querySelector('select, input:not([type="hidden"]), textarea');
                if (firstField) firstField.focus({ preventScroll: true });
            }
        });

        updateExpandedState();

        mobileViewport.addEventListener('change', function (event) {
            expanded = event.matches ? hasAppliedFilters(panel) : true;
            updateExpandedState();
        });
    });
});
