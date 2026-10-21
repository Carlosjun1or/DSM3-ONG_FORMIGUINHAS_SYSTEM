(() => {
    const impactoLista = document.querySelector('.impacto-indicadores');
    const impactoCards = impactoLista
        ? Array.from(impactoLista.querySelectorAll('.impacto-indicador'))
        : [];
    const impactoStatus = document.querySelector('[data-impacto-status]');

    if (impactoLista && impactoCards.length > 1 && impactoStatus) {
        impactoCards.forEach((card) => {
            const handle = card.querySelector('[data-arrastar-impacto]');
            handle?.setAttribute('aria-keyshortcuts', 'Alt+ArrowLeft Alt+ArrowRight Alt+ArrowUp Alt+ArrowDown');
        });

        const announcePosition = (card) => {
            const position = Array.from(impactoLista.children).indexOf(card) + 1;
            const label = card.querySelector('strong')?.textContent.trim();
            impactoStatus.textContent = `${label}, posição ${position} de ${impactoCards.length}.`;
        };

        const placeCard = (card, destinationIndex) => {
            const cards = Array.from(impactoLista.children);
            const currentIndex = cards.indexOf(card);
            const boundedIndex = Math.max(0, Math.min(destinationIndex, cards.length - 1));

            if (boundedIndex === currentIndex) {
                return false;
            }

            const destination = cards[boundedIndex];
            if (currentIndex < boundedIndex) {
                impactoLista.insertBefore(card, destination.nextSibling);
            } else {
                impactoLista.insertBefore(card, destination);
            }

            announcePosition(card);
            return true;
        };

        impactoLista.addEventListener('keydown', (event) => {
            const card = event.target.closest('.impacto-indicador');
            if (!card || !event.target.matches('[data-arrastar-impacto]') || !event.altKey) {
                return;
            }

            const columns = getComputedStyle(impactoLista).gridTemplateColumns.split(' ').length;
            const moves = {
                ArrowLeft: -1,
                ArrowRight: 1,
                ArrowUp: -columns,
                ArrowDown: columns
            };
            const move = moves[event.key];

            if (move !== undefined) {
                event.preventDefault();
                placeCard(card, Array.from(impactoLista.children).indexOf(card) + move);
                card.focus();
            }
        });

        let pointerDrag = null;

        impactoLista.addEventListener('pointerdown', (event) => {
            const handle = event.target.closest('[data-arrastar-impacto]');
            const card = handle?.closest('.impacto-indicador');
            if (!card || event.button !== 0 || !event.isPrimary) {
                return;
            }

            pointerDrag = {
                card,
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                active: false,
                preview: null,
                target: null
            };
        });

        impactoLista.addEventListener('pointermove', (event) => {
            if (!pointerDrag || event.pointerId !== pointerDrag.pointerId) {
                return;
            }

            const deltaX = event.clientX - pointerDrag.startX;
            const deltaY = event.clientY - pointerDrag.startY;

            if (!pointerDrag.active && Math.hypot(deltaX, deltaY) < 8) {
                return;
            }

            if (!pointerDrag.active) {
                const bounds = pointerDrag.card.getBoundingClientRect();
                const preview = pointerDrag.card.cloneNode(true);
                preview.classList.remove('is-dragging', 'is-drop-target');
                preview.classList.add('impacto-drag-preview');
                preview.setAttribute('aria-hidden', 'true');
                preview.removeAttribute('tabindex');
                preview.querySelectorAll('button, [tabindex]').forEach((element) => {
                    element.tabIndex = -1;
                });
                preview.style.width = `${bounds.width}px`;
                preview.style.height = `${bounds.height}px`;
                document.body.append(preview);

                pointerDrag.preview = preview;
                pointerDrag.active = true;
                pointerDrag.card.classList.add('is-dragging');
                pointerDrag.card.setPointerCapture(event.pointerId);
            }

            event.preventDefault();
            pointerDrag.preview.style.left = `${event.clientX}px`;
            pointerDrag.preview.style.top = `${event.clientY}px`;

            const closestCard = impactoCards
                .filter((card) => card !== pointerDrag.card)
                .map((card) => {
                    const bounds = card.getBoundingClientRect();
                    const centerX = bounds.left + bounds.width / 2;
                    const centerY = bounds.top + bounds.height / 2;
                    return {
                        card,
                        distance: Math.hypot(event.clientX - centerX, event.clientY - centerY)
                    };
                })
                .sort((first, second) => first.distance - second.distance)[0];

            impactoLista.querySelectorAll('.is-drop-target').forEach((card) => {
                card.classList.remove('is-drop-target');
            });

            pointerDrag.target = closestCard && closestCard.distance < 180
                ? closestCard.card
                : null;
            pointerDrag.target?.classList.add('is-drop-target');
        });

        const finishPointerDrag = (event) => {
            if (!pointerDrag || event.pointerId !== pointerDrag.pointerId) {
                return;
            }

            const { card, target, preview, active } = pointerDrag;
            pointerDrag = null;
            preview?.remove();
            card.classList.remove('is-dragging');
            impactoLista.querySelectorAll('.is-drop-target').forEach((dropTarget) => {
                dropTarget.classList.remove('is-drop-target');
            });

            if (active && target) {
                placeCard(card, Array.from(impactoLista.children).indexOf(target));
            }
        };

        impactoLista.addEventListener('pointerup', finishPointerDrag);
        impactoLista.addEventListener('pointercancel', finishPointerDrag);
    }

    if (
        !('IntersectionObserver' in window) ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
        return;
    }

    const targets = document.querySelectorAll([
        '#inicio .cabecalho',
        '#inicio .inicio-conteudo',
        '#inicio .indicadores',
        '.impacto-cabecalho',
        '.impacto-indicador',
        '#historia .historia-conteudo > article',
        '#historia .pillar',
        '#multiroes .multiroes-conteudo > h2',
        '#multiroes .multiroes-conteudo > p',
        '#multiroes .multiroes-conteudo > strong',
        '#multiroes .multirao-card',
        '#multiroes .proximo-mutirao',
        '.apoie-cabecalho',
        '.apoie-pix-card',
        '#praias .praias-conteudo > *',
        '.praia-card',
        '.mutirao-calendario-card',
        '.public-announcements > .card',
        '.public-announcement-detail'
    ].join(','));
    if (!targets.length) {
        return;
    }

    document.documentElement.classList.add('scroll-reveal-ready');

    const observer = new IntersectionObserver((entries, activeObserver) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                if (entry.target.matches('.impacto-indicador')) {
                    const delay = impactoCards.indexOf(entry.target) * 110;
                    entry.target.style.transitionDelay = `${delay}ms`;
                    window.setTimeout(() => {
                        entry.target.style.removeProperty('transition-delay');
                    }, 650 + delay);
                }

                entry.target.classList.add('is-visible');
                activeObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.12,
        rootMargin: '0px 0px -6% 0px'
    });

    targets.forEach((target) => {
        target.classList.add('scroll-reveal');
        observer.observe(target);
    });
})();
