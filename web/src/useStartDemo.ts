// "Try the demo": create a throwaway account with sample film and land on
// Tendencies. A hosted API on a free tier can take a while to wake up, so the
// button says so (via the API client's slow-request tracking) instead of
// looking stuck.
import { useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, serverWaking } from "./api/client";
import { useStore } from "./useStore";

export function useStartDemo() {
  const { user, startDemo } = useStore();
  const navigate = useNavigate();
  const waking = useSyncExternalStore(serverWaking.subscribe, serverWaking.get);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = async () => {
    if (busy) return;
    // Already signed in (demo or real account): don't replace the session.
    if (user) {
      navigate("/tendencies");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await startDemo();
      navigate("/tendencies");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? "Too many demos from your network. Try again in an hour, or take the quiz."
          : "Couldn't start the demo. Try again in a minute."
      );
    } finally {
      setBusy(false);
    }
  };

  const label = !busy ? "Try the demo" : waking ? "Waking up the server…" : "Starting the demo…";
  return { start, busy, label, error };
}
