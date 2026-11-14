// "Try the demo": create a throwaway account with sample film and land on
// Tendencies. A hosted API on a free tier can take a while to wake up, so the
// button says so after a few seconds instead of looking stuck.
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "./api/client";
import { useStore } from "./useStore";

const SLOW_MS = 3000;

export function useStartDemo() {
  const { user, startDemo } = useStore();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const start = async () => {
    if (busy) return;
    // Already signed in (demo or real account): don't replace the session.
    if (user) {
      navigate("/tendencies");
      return;
    }
    setBusy(true);
    setError(null);
    timer.current = window.setTimeout(() => setSlow(true), SLOW_MS);
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
      window.clearTimeout(timer.current);
      setBusy(false);
      setSlow(false);
    }
  };

  const label = !busy ? "Try the demo" : slow ? "Waking up the server…" : "Starting the demo…";
  return { start, busy, label, error };
}
