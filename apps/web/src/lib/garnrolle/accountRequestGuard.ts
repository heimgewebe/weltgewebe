export type AccountRequestToken = Readonly<{
  accountId: string;
  generation: number;
}>;

export type AccountRequestGuard = {
  begin(accountId: string): AccountRequestToken;
  invalidate(): void;
  isCurrent(
    token: AccountRequestToken,
    currentAccountId: string | null,
  ): boolean;
};

/**
 * Keeps asynchronous account-bound reads from applying after the authenticated
 * account changes. Starting a new read or invalidating the guard makes every
 * earlier token stale.
 */
export function createAccountRequestGuard(): AccountRequestGuard {
  let generation = 0;
  let requestedAccountId: string | null = null;

  return {
    begin(accountId) {
      requestedAccountId = accountId;
      generation += 1;
      return { accountId, generation };
    },
    invalidate() {
      requestedAccountId = null;
      generation += 1;
    },
    isCurrent(token, currentAccountId) {
      return (
        token.generation === generation &&
        token.accountId === requestedAccountId &&
        token.accountId === currentAccountId
      );
    },
  };
}
