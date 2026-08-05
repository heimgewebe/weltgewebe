/**
 * Caches a successful dynamic import while dropping a rejected promise so a
 * later open can retry the network/chunk load instead of replaying the failure.
 */
export function createResettableLazyImport<T>(
  loader: () => Promise<T>,
): () => Promise<T> {
  let cached: Promise<T> | null = null;
  return () => {
    if (!cached) {
      cached = loader().catch((error) => {
        cached = null;
        throw error;
      });
    }
    return cached;
  };
}
