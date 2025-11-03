### 📄 weltgewebe/apps/web/src/lib/stores/governance.ts

**Größe:** 2 KB | **md5:** `2302c0165ea60ee88f6368d416add270`

```typescript
import { browser } from "$app/environment";
import { writable, type Subscriber, type Unsubscriber } from "svelte/store";

const TICK_MS = 1000;

/** Countdown-Store, der in festen Intervallen herunterzählt und nach Ablauf automatisch neu startet. */
export interface LoopingCountdown {
  subscribe: (run: Subscriber<number>) => Unsubscriber;
  /** Setzt den Countdown auf die Ausgangsdauer zurück und startet ihn erneut, falls er aktiv war. */
  reset: () => void;
}

/** Steuerungs-Store für einen booleschen Zustand mit sprechenden Convenience-Methoden. */
export interface BooleanToggle {
  subscribe: (run: Subscriber<boolean>) => Unsubscriber;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export function createLoopingCountdown(durationMs: number): LoopingCountdown {
  const { subscribe: internalSubscribe, set, update } = writable(durationMs);

  let interval: ReturnType<typeof setInterval> | null = null;
  let activeSubscribers = 0;

  const start = () => {
    if (!browser || interval !== null) return;
    interval = setInterval(() => {
      update((previous) => (previous > TICK_MS ? previous - TICK_MS : durationMs));
    }, TICK_MS);
  };

  const stop = () => {
    if (interval !== null) {
      clearInterval(interval);
      interval = null;
    }
    set(durationMs);
  };

  return {
    subscribe(run) {
      activeSubscribers += 1;
      if (activeSubscribers === 1) start();
      const unsubscribe = internalSubscribe(run);
      return () => {
        unsubscribe();
        activeSubscribers -= 1;
        if (activeSubscribers === 0) {
          stop();
        }
      };
    },
    reset() {
      if (!browser) return;
      stop();
      if (activeSubscribers > 0) start();
    }
  };
}

export function createBooleanToggle(initial = false): BooleanToggle {
  const { subscribe, set, update } = writable(initial);
  return {
    subscribe,
    open: () => set(true),
    close: () => set(false),
    toggle: () => update((value) => !value)
  };
}
```

### 📄 weltgewebe/apps/web/src/lib/stores/index.ts

**Größe:** 30 B | **md5:** `2578f505c899216949cce97e01d907b9`

```typescript
export * from "./governance";
```

