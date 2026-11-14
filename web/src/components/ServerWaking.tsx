// Shown while an API request has been pending for more than a few seconds,
// which on the free host almost always means it is waking from sleep.
import { useSyncExternalStore } from "react";
import { serverWaking } from "../api/client";

export default function ServerWaking() {
  const waking = useSyncExternalStore(serverWaking.subscribe, serverWaking.get);
  // The live region stays mounted so screen readers announce the text.
  return (
    <div className="server-waking" role="status">
      {waking && (
        <>
          <b>Waking up the server…</b> The free host sleeps when idle, so this
          can take up to a minute.
        </>
      )}
    </div>
  );
}
