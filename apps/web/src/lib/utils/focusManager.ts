import { tick } from "svelte";

const restoreTargets: Record<"search" | "filter", HTMLElement | null> = {
  search: null,
  filter: null,
};

export function setRestoreTarget(mode: "search" | "filter", el: HTMLElement) {
  restoreTargets[mode] = el;
}

export function restoreTarget(mode: "search" | "filter") {
  const el = restoreTargets[mode];
  if (el && typeof document !== "undefined") {
    // Check if focus is outside the current page body or already inside another valid input,
    // but typically we just restore focus back to the target safely.
    tick().then(() => {
      // Check if el is still in the document
      if (document.body.contains(el)) {
        try {
          el.focus();
        } catch {
          // ignore focus errors
        }
      }
    });
  }
  restoreTargets[mode] = null;
}
