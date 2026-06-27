/**
 * Simple request-deduplication utility.
 *
 * Tracks in-flight promises by a string key.  If a caller requests the same
 * key while a previous call is still pending, the existing promise is
 * returned instead of firing a duplicate network request.
 *
 * Example:
 *   const data = await dedup("fetchFund:000001", () => api.getFund("000001"));
 */

/** Map of active request keys → pending Promise */
const pending = new Map<string, Promise<unknown>>();

/**
 * Register (or reuse) a request under *key*.
 *
 * - If a request for *key* is already in flight, returns that promise.
 * - Otherwise calls *factory()*, stores the promise, and auto-cleans on
 *   settle (both success and failure).
 *
 * @param key      Unique identifier for the request (e.g. `"fundNav:000001"`)
 * @param factory  Async function that produces the desired result
 * @returns        Promise resolving to the factory's return value
 */
export async function dedup<T>(key: string, factory: () => Promise<T>): Promise<T> {
  const existing = pending.get(key);
  if (existing !== undefined) {
    return existing as Promise<T>;
  }

  const promise = factory();
  pending.set(key, promise);

  // Clean up once settled — re-throw to propagate the error
  try {
    const result = await promise;
    return result;
  } finally {
    // Remove *this specific promise* only — if another caller has already
    // replaced the entry we must not clobber it.
    if (pending.get(key) === promise) {
      pending.delete(key);
    }
  }
}

/**
 * Manually remove a pending request (e.g. for cancellation / retry logic).
 */
export function clearDedupKey(key: string): void {
  pending.delete(key);
}

/**
 * Remove all tracked pending requests (useful in tests or logout flows).
 */
export function clearAllDedupKeys(): void {
  pending.clear();
}
