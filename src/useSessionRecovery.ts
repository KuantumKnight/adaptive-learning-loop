import { useEffect, useState } from "react";
import { api, type Session } from "./api";

/** Restore only sessions that still have a bearer token in this browser. */
export function useSessionRecovery() {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("idp.session");
      if (!saved) return;
      const parsed = JSON.parse(saved) as Session;
      if (!parsed?.session_id || !parsed?.access_token) throw new Error("Invalid saved session");
      api.setSessionToken(parsed.access_token);
      setSession(parsed);
    } catch {
      localStorage.removeItem("idp.session");
    }
  }, []);
  function exit() {
    localStorage.removeItem("idp.session");
    setSession(null);
  }
  return { session, setSession, exit };
}
