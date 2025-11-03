### 📄 apps/web/src/lib/utils/inert-polyfill.ts

**Größe:** 2 KB | **md5:** `7827c363e57b5dfc9af1dd8169d37ef4`

```typescript
// Minimaler inert-Polyfill:
// - blockiert Focus & Clicks in [inert]
// - setzt aria-hidden, solange inert aktiv ist
// Safari < 16.4 & ältere iPadOS-Versionen profitieren davon.

function applyAriaHidden(el: Element, on: boolean) {
  const prev = (el as HTMLElement).getAttribute('aria-hidden');
  if (on) {
    if (prev !== 'true') (el as HTMLElement).setAttribute('aria-hidden', 'true');
  } else {
    if (prev === 'true') (el as HTMLElement).removeAttribute('aria-hidden');
  }
}

export function ensureInertPolyfill() {
  // Moderne Browser haben bereits inert-Unterstützung.
  if ('inert' in HTMLElement.prototype) return;

  // Style-Schutz zusätzlich (Pointer & Selection aus).
  const style = document.createElement('style');
  style.textContent = `
    [inert] { pointer-events:none; user-select:none; -webkit-user-select:none; -webkit-tap-highlight-color: transparent; }
  `;
  document.head.appendChild(style);

  // Aria-Hidden initial anwenden
  const syncAll = () => {
    document.querySelectorAll<HTMLElement>('[inert]').forEach((el) => applyAriaHidden(el, true));
  };
  syncAll();

  // Fokus- & Click-Blocker
  document.addEventListener('focusin', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      (t as HTMLElement).blur?.();
      (document.activeElement as HTMLElement | null)?.blur?.();
    }
  }, true);
  document.addEventListener('click', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  // Reagiere auf spätere inert-Attribute
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      if (!(m.target instanceof HTMLElement)) continue;
      if (m.type === 'attributes' && m.attributeName === 'inert') {
        const el = m.target as HTMLElement;
        const on = el.hasAttribute('inert');
        applyAriaHidden(el, on);
      }
    }
  });
  mo.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['inert'] });
}
```

### 📄 apps/web/src/lib/utils/ua-flags.ts

**Größe:** 187 B | **md5:** `47cbc1d02f91baf7dfb2478070899b75`

```typescript
export function setUAClasses() {
  const ua = navigator.userAgent || '';
  const isAndroid = /Android/i.test(ua);
  if (isAndroid) document.documentElement.classList.add('ua-android');
}
```

