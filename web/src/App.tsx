import { startTransition, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useStore } from "./useStore";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Teams from "./pages/Teams";
import Upload from "./pages/Upload";
import Tendencies from "./pages/Tendencies";
import Predict from "./pages/Predict";
import Vocabulary from "./pages/Vocabulary";
import Quiz from "./pages/Quiz";
import ServerWaking from "./components/ServerWaking";
import "./site.css";
import "./app.css";

const APP_LINKS = [
  ["/tendencies", "Tendencies"],
  ["/predict", "Predict"],
  ["/upload", "Upload"],
  ["/vocabulary", "Vocabulary"],
  ["/teams", "Teams"],
] as const;

function TeamPicker() {
  const { teams, activeTeam, setActiveTeam } = useStore();
  if (teams.length === 0) return null;
  return (
    <select
      aria-label="Active team"
      value={activeTeam?.id ?? ""}
      onChange={(e) =>
        setActiveTeam(teams.find((t) => t.id === Number(e.target.value)) ?? null)
      }
    >
      {teams.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );
}

const BANNER_KEY = "engage8_demo_banner_hidden";

function DemoBanner({ userId }: { userId: number }) {
  const [hidden, setHidden] = useState(
    () => localStorage.getItem(BANNER_KEY) === String(userId)
  );
  if (hidden) return null;
  return (
    <div className="demo-banner" role="note">
      <span>
        <b>Demo account.</b> Central HS is a fictional opponent with sample film.
        This account and its data are deleted after 24 hours.
      </span>
      <button
        className="btn btn-sm btn-line"
        aria-label="Dismiss demo notice"
        onClick={() => {
          localStorage.setItem(BANNER_KEY, String(userId));
          setHidden(true);
        }}
      >
        Dismiss
      </button>
    </div>
  );
}

function Shell() {
  const { user, logout } = useStore();
  const navigate = useNavigate();
  return (
    <div className="e8">
      <div className="e8-page">
        <header className="nav app-nav">
          <Link className="app-brand" to="/">
            <i aria-hidden="true" />
            Engage Eight
          </Link>
          <nav className="app-links" aria-label="App">
            {APP_LINKS.map(([to, label]) => (
              <NavLink key={to} className="nav-link" to={to}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="app-account">
            <TeamPicker />
            <span className="app-who">{user?.is_demo ? "Demo account" : user?.email}</span>
            <button
              className="btn btn-sm btn-line"
              onClick={() => {
                // Router navigations run as transitions; logging out in the same
                // transition stops the login gate from rendering in between.
                navigate("/");
                startTransition(logout);
              }}
            >
              {user?.is_demo ? "End demo" : "Sign out"}
            </button>
          </div>
        </header>
        <main className="app-main">
          {user?.is_demo && <DemoBanner userId={user.id} />}
          <Routes>
            <Route path="/tendencies" element={<Tendencies />} />
            <Route path="/predict" element={<Predict />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/vocabulary" element={<Vocabulary />} />
            <Route path="/teams" element={<Teams />} />
            <Route path="*" element={<Navigate to="/tendencies" replace />} />
          </Routes>
        </main>
        <p className="app-foot">
          Run/pass model trained on NFL play-by-play from nflverse. Your film
          is private to your account.
        </p>
      </div>
    </div>
  );
}

const Loading = () => (
  <div className="e8">
    <div className="e8-page">
      <p className="app-loading" role="status">
        Loading…
      </p>
    </div>
  </div>
);

/** /login: signed-in users go back to where they were headed. */
function LoginRoute() {
  const { user, loading } = useStore();
  const location = useLocation();
  if (loading) return <Loading />;
  if (user) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from ?? "/tendencies"} replace />;
  }
  return <Login />;
}

/** Everything else needs an account. */
function Gate() {
  const { user, loading } = useStore();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Shell />;
}

export default function App() {
  // The landing page and the quiz are public; the quiz is static JSON and
  // works even while the hosted API is asleep. The landing page's demo button
  // shows its own cold-start message, so the shared notice is only on the
  // pages that talk to the API.
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/quiz" element={<Quiz />} />
      <Route path="/login" element={<><LoginRoute /><ServerWaking /></>} />
      <Route path="*" element={<><Gate /><ServerWaking /></>} />
    </Routes>
  );
}
