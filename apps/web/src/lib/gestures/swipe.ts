/**
 * Robuste horizontale Swipe-Action für Svelte (Touch/Pen).
 * - Pointer-ID + set/releasePointerCapture → verliert Events nicht
 * - angleGate + velocityGate + lengthThreshold → zuverlässig, aber nicht nervös
 * - Cancel/Leave-Handling
 *
 * Verwendung:
 *   <div use:swipe={{ onLeft, onRight, threshold: 30 }} class="swipeable">…</div>
 *   .swipeable {
 *     touch-action: pan-y;            // lässt vertikales Scrollen zu und schützt horizontale Swipes
 *     overscroll-behavior-x: contain; // verhindert seitliches Überscrollen
 *   }
 *   Hinweis: Eltern-Container sollten horizontales Snap/Scroll vermeiden
 *   (siehe Styles in `app.css`, Klasse `.swipe-parent { scroll-snap-type: none; }`).
 */
export type SwipeDirection = "left" | "right";
export type SwipeMeta = { dx: number; dy: number; v: number };
export type SwipeRejectMeta = {
  dx: number;
  dy: number;
  v: number;
  horizontalEnough: boolean;
  longEnough: boolean;
  fastEnough: boolean;
};

export type SwipeOptions = {
  threshold?: number; // minimale Strecke in px (Default 24)
  angleRatio?: number; // |dy| <= angleRatio * |dx| (Default 0.5)
  velocityMin?: number; // minimale Geschwindigkeit px/ms (Default 0.30)
  allowMouse?: boolean; // Maus-Swipes erlauben (Default false)
  lockAxis?: boolean; // bricht ab, wenn Vertikalbewegung dominiert
  passiveMove?: boolean; // pointermove passiv halten (Default true)
  axisDeadzone?: number; // Radius bevor lockAxis greift (Default 6)
  onLeft?: () => void; // callback bei Swipe nach links
  onRight?: () => void; // callback bei Swipe nach rechts
  onSwipe?: (dir: SwipeDirection, meta: SwipeMeta) => void; // generischer Callback
  onReject?: (meta: SwipeRejectMeta) => void; // Debugging-Hook bei nicht erfüllten Gates
};

type Pt = { x: number; y: number; t: number };

const PASSIVE_TRUE_OPTIONS: AddEventListenerOptions = { passive: true };
const PASSIVE_FALSE_OPTIONS: AddEventListenerOptions = { passive: false };

type SwipeConfig = {
  threshold: number;
  angleRatio: number;
  velocityMin: number;
  allowMouse: boolean;
  lockAxis: boolean;
  passiveMove: boolean;
  axisDeadzone: number;
  onLeft?: () => void;
  onRight?: () => void;
  onSwipe?: (dir: SwipeDirection, meta: SwipeMeta) => void;
  onReject?: (meta: SwipeRejectMeta) => void;
};

export function swipe(node: HTMLElement, opts: SwipeOptions = {}) {
  const cfg: SwipeConfig = {
    threshold: 24,
    angleRatio: 0.5,
    velocityMin: 0.3,
    allowMouse: false,
    lockAxis: false,
    passiveMove: true,
    axisDeadzone: 6,
    ...opts,
  };

  if (typeof window === "undefined") {
    return {
      destroy() {},
      update(next: SwipeOptions) {
        Object.assign(cfg, next);
      },
    };
  }

  let pid: number | null = null;
  let start: Pt | null = null;
  let last: Pt | null = null;
  let active = false;

  const now = () =>
    typeof performance !== "undefined" ? performance.now() : Date.now();

  function onDown(e: PointerEvent) {
    // Nur echte Touch/Pen-Gesten werten (verhindert „künstliche“ Maus-Swipes)
    const pointerAllowed =
      e.pointerType === "touch" ||
      e.pointerType === "pen" ||
      (cfg.allowMouse && e.pointerType === "mouse");

    if (!pointerAllowed) return;
    if (e.isPrimary === false) return;
    if (pid !== null) return; // bereits aktiv
    pid = e.pointerId;
    start = last = { x: e.clientX, y: e.clientY, t: now() };
    active = true;
    try {
      node.setPointerCapture(pid);
    } catch (err) {
      // setPointerCapture may fail in some browsers or if the element is not in the DOM.
      // This is non-fatal for swipe handling, so we ignore the error.
      // In development, log the error for debugging.
      if (import.meta.env.DEV) {
        console.error("setPointerCapture failed:", err);
      }
    }
  }

  function onMove(e: PointerEvent) {
    if (!active || e.pointerId !== pid || !start) return;
    if (e.isPrimary === false) return;

    if (!cfg.passiveMove) e.preventDefault();

    if (cfg.lockAxis) {
      const dx = e.clientX - start.x;
      const dy = e.clientY - start.y;
      if (Math.abs(dx) < cfg.axisDeadzone && Math.abs(dy) < cfg.axisDeadzone) {
        // erst mal genug Daten sammeln
      } else if (Math.abs(dy) > Math.abs(dx)) {
        reset();
        return;
      }
    }

    last = { x: e.clientX, y: e.clientY, t: now() };
    // Standardmäßig passiv, kann über passiveMove=false deaktiviert werden
  }

  function finalize(end: Pt) {
    if (!start) return;
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dt = Math.max(1, end.t - start.t);
    const v = Math.abs(dx) / dt; // px/ms
    const horizontalEnough = Math.abs(dy) <= cfg.angleRatio * Math.abs(dx);
    const longEnough = Math.abs(dx) >= cfg.threshold;
    const fastEnough = v >= cfg.velocityMin;
    if (horizontalEnough && longEnough && fastEnough) {
      const dir: SwipeDirection = dx < 0 ? "left" : "right";
      cfg.onSwipe?.(dir, { dx, dy, v });
      if (dir === "left") {
        cfg.onLeft?.();
      } else {
        cfg.onRight?.();
      }
    } else {
      cfg.onReject?.({ dx, dy, v, horizontalEnough, longEnough, fastEnough });
    }
  }

  function reset() {
    if (pid !== null) {
      try {
        node.releasePointerCapture(pid);
      } catch (err) {
        // Some browsers may throw if releasePointerCapture is called incorrectly.
        // This error is safe to ignore, but log in development for debugging.
        if (import.meta.env.DEV) {
          console.error("releasePointerCapture failed:", err);
        }
      }
    }
    pid = null;
    start = null;
    last = null;
    active = false;
  }

  function onUp(e: PointerEvent) {
    if (!active || e.pointerId !== pid) return;
    if (e.isPrimary === false) return;
    finalize(last ?? { x: e.clientX, y: e.clientY, t: now() });
    reset();
  }

  function onCancel(e: PointerEvent) {
    if (e.pointerId !== pid) return;
    reset();
  }

  node.addEventListener("pointerdown", onDown, PASSIVE_TRUE_OPTIONS);
  node.addEventListener(
    "pointermove",
    onMove,
    cfg.passiveMove ? PASSIVE_TRUE_OPTIONS : PASSIVE_FALSE_OPTIONS,
  );
  node.addEventListener("pointerup", onUp, PASSIVE_TRUE_OPTIONS);
  node.addEventListener("pointercancel", onCancel, PASSIVE_TRUE_OPTIONS);
  node.addEventListener("pointerleave", onCancel, PASSIVE_TRUE_OPTIONS);
  node.addEventListener("lostpointercapture", onCancel, PASSIVE_TRUE_OPTIONS);

  let detachWindowUp: (() => void) | null = null;
  if (typeof window !== "undefined") {
    const onWindowUp = (e: PointerEvent) => {
      if (e.pointerId === pid) {
        onUp(e);
      }
    };
    window.addEventListener("pointerup", onWindowUp, PASSIVE_TRUE_OPTIONS);
    detachWindowUp = () => window.removeEventListener("pointerup", onWindowUp);
  }

  let cleanupVisibility: (() => void) | null = null;
  if (typeof document !== "undefined") {
    const onVis = () => {
      if (document.hidden) reset();
    };
    document.addEventListener("visibilitychange", onVis, PASSIVE_TRUE_OPTIONS);
    cleanupVisibility = () => {
      document.removeEventListener("visibilitychange", onVis);
    };
  }

  return {
    destroy() {
      node.removeEventListener("pointerdown", onDown);
      node.removeEventListener("pointermove", onMove);
      node.removeEventListener("pointerup", onUp);
      node.removeEventListener("pointercancel", onCancel);
      node.removeEventListener("pointerleave", onCancel);
      node.removeEventListener("lostpointercapture", onCancel);
      detachWindowUp?.();
      cleanupVisibility?.();
    },
    update(next: SwipeOptions) {
      const prevPassiveMove = cfg.passiveMove;
      Object.assign(cfg, next);
      if (cfg.passiveMove !== prevPassiveMove) {
        node.removeEventListener("pointermove", onMove);
        node.addEventListener(
          "pointermove",
          onMove,
          cfg.passiveMove ? PASSIVE_TRUE_OPTIONS : PASSIVE_FALSE_OPTIONS,
        );
      }
    },
  };
}
