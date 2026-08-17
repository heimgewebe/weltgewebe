import { derived, get, writable, type Readable } from "svelte/store";
import { accountAttentionInvalidation } from "$lib/accountAttention";
import {
  listDirectConversations,
  type DirectConversation,
} from "$lib/api/directMessages";
import { listProposals, type Proposal } from "$lib/api/governance";
import { authStore, type AuthRole, type AuthStatus } from "$lib/auth/store";
import {
  hasAcceptedWeberApplication,
  hasPendingWeberApplication,
  projectTopBarAttention,
  type AttentionItem,
} from "$lib/components/topBarAttentionState";

export type WeberApplicationState = "unknown" | "available" | "pending";

export interface AccountAttentionState {
  accountId: string;
  role: AuthRole;
  weberApplicationState: WeberApplicationState;
  conversations: DirectConversation[];
  proposals: Proposal[];
  items: AttentionItem[];
}

export interface AccountAttentionControllerDependencies {
  getAuthStatus: () => AuthStatus;
  checkAuth: (options?: { force?: boolean }) => Promise<AuthStatus>;
  listDirectConversations: () => Promise<DirectConversation[]>;
  listProposals: () => Promise<Proposal[]>;
}

export interface AccountAttentionController extends Readable<AccountAttentionState> {
  refresh: (status?: AuthStatus) => Promise<void>;
  refreshMessages: (status?: AuthStatus) => Promise<void>;
}

const MESSAGE_POLL_MS = 30_000;

function initialState(): AccountAttentionState {
  return {
    accountId: "",
    role: "gast",
    weberApplicationState: "unknown",
    conversations: [],
    proposals: [],
    items: [],
  };
}

export function maskAccountAttentionForAuth(
  state: AccountAttentionState,
  status: AuthStatus,
): AccountAttentionState {
  const accountId = status.account_id;
  if (!status.authenticated || !accountId || state.accountId !== accountId) {
    return { ...initialState(), role: status.role };
  }
  if (state.role === status.role) return state;

  return {
    ...state,
    role: status.role,
    weberApplicationState:
      status.role === "gast" ? state.weberApplicationState : "unknown",
    items: projectTopBarAttention({
      conversations: state.conversations,
      proposals: state.proposals,
      accountId,
      role: status.role,
    }),
  };
}

export function createAccountAttentionController(
  dependencies: AccountAttentionControllerDependencies,
): AccountAttentionController {
  const store = writable<AccountAttentionState>(initialState());
  let observedAccountId = "";
  let observedRole: AuthRole = "gast";
  let messageRequestRevision = 0;
  let proposalRequestRevision = 0;

  function ownsResult(accountId: string): boolean {
    const current = dependencies.getAuthStatus();
    return (
      current.authenticated &&
      current.account_id === accountId &&
      observedAccountId === accountId
    );
  }

  function project(state: AccountAttentionState): AccountAttentionState {
    return {
      ...state,
      items: projectTopBarAttention({
        conversations: state.conversations,
        proposals: state.proposals,
        accountId: state.accountId || undefined,
        role: state.role,
      }),
    };
  }

  function reset(accountId = "", role: AuthRole = "gast"): void {
    observedAccountId = accountId;
    observedRole = role;
    messageRequestRevision += 1;
    proposalRequestRevision += 1;
    store.set({ ...initialState(), accountId, role });
  }

  function prepare(status: AuthStatus): boolean {
    const accountId = status.account_id;
    if (!status.authenticated || !accountId) {
      reset();
      return false;
    }
    if (observedAccountId !== accountId) {
      reset(accountId, status.role);
      return true;
    }
    if (observedRole !== status.role) {
      observedRole = status.role;
      store.update((state) =>
        project({
          ...state,
          role: status.role,
          weberApplicationState:
            status.role === "gast" ? state.weberApplicationState : "unknown",
        }),
      );
    }
    return true;
  }

  async function refreshMessages(status = dependencies.getAuthStatus()) {
    if (!prepare(status)) return;
    const accountId = status.account_id;
    if (!accountId) return;

    const revision = ++messageRequestRevision;
    try {
      const conversations = await dependencies.listDirectConversations();
      if (revision !== messageRequestRevision || !ownsResult(accountId)) return;
      store.update((state) => project({ ...state, conversations }));
    } catch {
      // Preserve the last confirmed projection. A transient failure must never
      // turn unread work into a false empty state.
    }
  }

  async function refreshProposals(status = dependencies.getAuthStatus()) {
    if (!prepare(status)) return;
    const accountId = status.account_id;
    if (!accountId) return;

    const revision = ++proposalRequestRevision;
    try {
      const proposals = await dependencies.listProposals();
      if (revision !== proposalRequestRevision || !ownsResult(accountId))
        return;

      let weberApplicationState: WeberApplicationState = "unknown";
      let acceptedApplicationNeedsAuthRefresh = false;
      if (status.role === "gast") {
        const pending = hasPendingWeberApplication(proposals, accountId);
        const accepted = hasAcceptedWeberApplication(proposals, accountId);
        weberApplicationState = pending || accepted ? "pending" : "available";
        acceptedApplicationNeedsAuthRefresh = !pending && accepted;
      }

      store.update((state) =>
        project({ ...state, proposals, weberApplicationState }),
      );

      if (acceptedApplicationNeedsAuthRefresh && ownsResult(accountId)) {
        // Governance can finalize a guest application before the auth endpoint
        // reflects the promoted role. Keep the non-actionable pending state
        // until the authoritative auth read confirms the transition.
        await dependencies.checkAuth({ force: true });
      }
    } catch {
      // Preserve the last confirmed projection. In particular, an initial
      // proposal failure must not look like permission to submit a new request.
    }
  }

  async function refresh(status = dependencies.getAuthStatus()) {
    if (!prepare(status)) return;
    await Promise.all([refreshMessages(status), refreshProposals(status)]);
  }

  return {
    subscribe: store.subscribe,
    refresh,
    refreshMessages,
  };
}

const controller = createAccountAttentionController({
  getAuthStatus: () => get(authStore),
  checkAuth: (options) => authStore.checkAuth(options),
  listDirectConversations: () => listDirectConversations(),
  listProposals: () => listProposals(),
});

export const accountAttentionRuntime: Readable<AccountAttentionState> = derived(
  [controller, authStore],
  ([state, status]) => maskAccountAttentionForAuth(state, status),
);

export function refreshAccountAttention(): Promise<void> {
  return controller.refresh(get(authStore));
}

let retainCount = 0;
let stopRuntime: (() => void) | null = null;

function installRuntime(): () => void {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return () => undefined;
  }

  // null forces the first subscription event to reconcile even when the
  // current auth state is unauthenticated. The controller store outlives the
  // map component, so skipping that first empty key could briefly expose the
  // previous account's retained attention after a client-side remount.
  let authKey: string | null = null;
  const unsubscribeAuth = authStore.subscribe((status) => {
    const nextAuthKey = status.authenticated
      ? `${status.account_id ?? ""}:${status.role}`
      : "";
    if (nextAuthKey === authKey) return;
    authKey = nextAuthKey;
    void controller.refresh(status);
  });

  let attentionSignalPrimed = false;
  const unsubscribeAttention = accountAttentionInvalidation.subscribe(() => {
    if (!attentionSignalPrimed) {
      attentionSignalPrimed = true;
      return;
    }
    void refreshAccountAttention();
  });

  const refreshWhenVisible = () => {
    if (document.visibilityState === "visible") void refreshAccountAttention();
  };
  const refreshOnFocus = () => void refreshAccountAttention();
  const messagePoll = window.setInterval(() => {
    if (document.visibilityState === "visible") {
      void controller.refreshMessages(get(authStore));
    }
  }, MESSAGE_POLL_MS);

  document.addEventListener("visibilitychange", refreshWhenVisible);
  window.addEventListener("focus", refreshOnFocus);

  return () => {
    unsubscribeAuth();
    unsubscribeAttention();
    window.clearInterval(messagePoll);
    document.removeEventListener("visibilitychange", refreshWhenVisible);
    window.removeEventListener("focus", refreshOnFocus);
  };
}

export function retainAccountAttentionRuntime(): () => void {
  retainCount += 1;
  if (!stopRuntime) stopRuntime = installRuntime();
  let released = false;
  return () => {
    if (released) return;
    released = true;
    retainCount = Math.max(0, retainCount - 1);
    if (retainCount === 0 && stopRuntime) {
      stopRuntime();
      stopRuntime = null;
    }
  };
}
