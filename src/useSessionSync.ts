import { useCallback, useRef } from "react";
import { api, type ProgressRequest } from "./api";

/** Serialize progress writes so an older heartbeat cannot overwrite a transition. */
export function useSessionSync(sessionId: string) {
  const chain = useRef<Promise<unknown>>(Promise.resolve());
  const pending = useRef(0);
  const save = useCallback((progress: ProgressRequest) => {
    pending.current += 1;
    const next = chain.current.then(() => api.progress(sessionId, progress));
    chain.current = next.catch(() => undefined).finally(() => { pending.current -= 1; });
    return next;
  }, [sessionId]);
  const isPending = useCallback(() => pending.current > 0, []);
  return { save, isPending };
}
