// Sign in / create an account, in the landing page's style. The left panel
// offers the no-account ways in (demo, quiz) so nobody hits a dead end.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useStore } from "../useStore";
import { ApiError } from "../api/client";
import SiteNav from "../components/SiteNav";
import { useStartDemo } from "../useStartDemo";

export default function Login() {
  const { login, signup } = useStore();
  const demo = useStartDemo();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const signingUp = mode === "signup";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (signingUp) await signup(email, password);
      else await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="e8">
      <div className="e8-page">
        <SiteNav page="login" />
        <main className="auth">
          <section className="auth-intro">
            <div>
              <h1 className="auth-hl cond">
                <span>Scout</span>
                <span className="is-acc">the call.</span>
              </h1>
              <p className="auth-lede">
                Upload your opponent's Hudl film, see what they run in every
                situation, and get a run/pass read that leans on their own
                tendencies.
              </p>
            </div>
            <div className="auth-alt">
              <small>No account? Look around first.</small>
              <div className="row">
                <button
                  className="btn btn-md btn-line"
                  onClick={demo.start}
                  aria-busy={demo.busy}
                >
                  {demo.label}
                </button>
                <Link className="btn btn-md btn-line" to="/quiz">
                  Take the quiz
                </Link>
              </div>
              {demo.error && (
                <div className="msg error" role="alert">
                  {demo.error}
                </div>
              )}
            </div>
          </section>

          <section className="auth-card" aria-labelledby="auth-title">
            <h2 id="auth-title" className="auth-title cond">
              {signingUp ? "Create account" : "Sign in"}
            </h2>
            <p className="auth-sub">
              {signingUp
                ? "Your teams and film stay private to your account."
                : "Welcome back. Your teams and film are where you left them."}
            </p>
            <form className="auth-form stack" onSubmit={submit}>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              <label className="field">
                <span>Password</span>
                <input
                  type="password"
                  autoComplete={signingUp ? "new-password" : "current-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={signingUp ? 10 : undefined}
                  required
                />
                {signingUp && <small>At least 10 characters.</small>}
              </label>
              {error && (
                <div className="msg error" role="alert">
                  {error}
                </div>
              )}
              <button className="btn btn-light" disabled={busy} aria-busy={busy}>
                {busy ? "One moment…" : signingUp ? "Create account" : "Sign in"}
              </button>
            </form>
            <p className="auth-switch">
              {signingUp ? "Have an account?" : "No account?"}{" "}
              <button
                type="button"
                className="linkish"
                onClick={() => {
                  setError(null);
                  setMode(signingUp ? "login" : "signup");
                }}
              >
                {signingUp ? "Sign in" : "Create one"}
              </button>
            </p>
          </section>
        </main>
      </div>
    </div>
  );
}
