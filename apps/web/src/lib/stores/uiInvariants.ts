import { derived } from "svelte/store";
import type { Writable } from "svelte/store";
import type { SystemState, Selection, KompositionDraft } from "./uiView";

export function assertUiStateInvariant(
  state: SystemState,
  sel: Selection,
  draft: KompositionDraft,
) {
  if (sel !== null && draft !== null) {
    throw new Error(
      "Invariant Violation: selection and kompositionDraft cannot both be set at the same time",
    );
  }
  if (state === "fokus" && !sel) {
    throw new Error(
      "Invariant Violation: systemState is 'fokus' but selection is null",
    );
  }
  if (state === "navigation" && sel) {
    throw new Error(
      "Invariant Violation: systemState is 'navigation' but selection is not null",
    );
  }
  if (state === "komposition" && !draft) {
    throw new Error(
      "Invariant Violation: systemState is 'komposition' but kompositionDraft is null",
    );
  }
  if (state !== "komposition" && draft) {
    throw new Error(
      "Invariant Violation: systemState is not 'komposition' but kompositionDraft is not null",
    );
  }
}

export function setupUiInvariantWatcher(
  systemState: Writable<SystemState>,
  selection: Writable<Selection>,
  kompositionDraft: Writable<KompositionDraft>,
) {
  // Fallback for environments where import.meta.env is not available
  const isDevOrTest =
    (typeof import.meta !== "undefined" &&
      import.meta.env &&
      (import.meta.env.DEV || import.meta.env.MODE === "test")) ||
    (typeof process !== "undefined" && process.env.NODE_ENV === "test");

  if (isDevOrTest) {
    let latestSnapshot: {
      $state: SystemState;
      $sel: Selection;
      $draft: KompositionDraft;
    } | null = null;
    let isValidationQueued = false;

    derived(
      [systemState, selection, kompositionDraft],
      ([$state, $sel, $draft]) => ({ $state, $sel, $draft }),
    ).subscribe((snapshot) => {
      latestSnapshot = snapshot;

      if (!isValidationQueued) {
        isValidationQueued = true;
        queueMicrotask(() => {
          isValidationQueued = false;
          if (!latestSnapshot) return;

          const { $state, $sel, $draft } = latestSnapshot;

          assertUiStateInvariant($state, $sel, $draft);
        });
      }
    });
  }
}
