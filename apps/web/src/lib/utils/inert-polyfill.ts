// Minimaler inert-Polyfill:
// - blockiert Focus & Clicks in [inert]
// - setzt aria-hidden, solange inert aktiv ist
// Safari < 16.4 & ältere iPadOS-Versionen profitieren davon.

const previousAriaHidden = new WeakMap<Element, string | null>();

function applyAriaHidden(el: Element, on: boolean) {
  const element = el as HTMLElement;

  if (on) {
    if (!previousAriaHidden.has(element)) {
      previousAriaHidden.set(element, element.getAttribute('aria-hidden'));
    }

    if (element.getAttribute('aria-hidden') !== 'true') {
      element.setAttribute('aria-hidden', 'true');
    }
    return;
  }

  const previous = previousAriaHidden.get(element);
  previousAriaHidden.delete(element);

  if (previous === undefined) {
    if (element.getAttribute('aria-hidden') === 'true') {
      element.removeAttribute('aria-hidden');
    }
    return;
  }

  if (previous === null) {
    element.removeAttribute('aria-hidden');
  } else {
    element.setAttribute('aria-hidden', previous);
  }
}

let hasSetupCompleted = false;

export function ensureInertPolyfill() {
  // SSR-Schutz und moderne Browser mit nativer inert-Unterstützung überspringen.
  if (typeof document === 'undefined' || typeof HTMLElement === 'undefined') return;
  if ('inert' in HTMLElement.prototype) return;
  if (hasSetupCompleted) return;
  hasSetupCompleted = true;

  // Style-Schutz nur einmal injizieren (Pointer & Selection aus).
  const styleId = 'wg-inert-polyfill-style';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      [inert] {
        pointer-events: none;
        user-select: none;
        -webkit-user-select: none;
        -webkit-tap-highlight-color: transparent;
      }
    `;
    document.head.appendChild(style);
  }

  // Aria-Hidden initial anwenden
  const syncAll = () => {
    document.querySelectorAll<HTMLElement>('[inert]').forEach((el) => applyAriaHidden(el, true));
  };
  syncAll();

  // Fokus-, Click- & Tastatur-Blocker
  document.addEventListener('focusin', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      (t as HTMLElement).blur?.();
      (document.activeElement as HTMLElement | null)?.blur?.();
    }
  }, { capture: true });
  document.addEventListener('click', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, { capture: true });
  document.addEventListener('keydown', (e) => {
    const active = document.activeElement as HTMLElement | null;
    const target = e.target as HTMLElement | null;
    const withinInert = (node: HTMLElement | null) => !!node && !!node.closest?.('[inert]');
    if (withinInert(active) || withinInert(target)) {
      if (e.key === 'Tab') {
        e.preventDefault();
        e.stopPropagation();
        active?.blur?.();
        return;
      }

      if (e.key === ' ' || e.key === 'Spacebar' || e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();
      }
    }
  }, { capture: true });

  // Reagiere auf spätere inert-Attribute
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === 'attributes' && m.attributeName === 'inert' && m.target instanceof HTMLElement) {
        const el = m.target as HTMLElement;
        const on = el.hasAttribute('inert');
        applyAriaHidden(el, on);
        continue;
      }

      if (m.type === 'childList') {
        for (const node of m.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;

          if (node.hasAttribute('inert')) {
            applyAriaHidden(node, true);
          }

          node.querySelectorAll('[inert]').forEach((el) => applyAriaHidden(el, true));
        }
      }
    }
  });
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['inert'], childList: true, subtree: true });
}
