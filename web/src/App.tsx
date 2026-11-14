import { startTransition, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
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

function TeamPicker() {
  const { teams, activeTeam, setActiveTeam } = useStore();
  if (teams.length === 0) return null;
  return (
    <select
      value={activeTeam?.id ?? ""}
      onChange={(e) =>
        setActiveTeam(teams.find((t) => t.id === Number(e.target.value)) ?? null)
      }
      style={{ width: "100%", marginBottom: 12 }}
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
        className="secondary"
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
    <div className="app">
      <nav className="sidebar">
        <div className="brand">
          Engage Eight
          <small>pre-snap scouting</small>
        </div>
        <TeamPicker />
        <NavLink className="nav-link" to="/tendencies">
          Tendencies
        </NavLink>
        <NavLink className="nav-link" to="/predict">
          Predict / Recommend
        </NavLink>
        <NavLink className="nav-link" to="/upload">
          Upload
        </NavLink>
        <NavLink className="nav-link" to="/vocabulary">
          Vocabulary
        </NavLink>
        <NavLink className="nav-link" to="/teams">
          Teams
        </NavLink>
        <div className="sidebar-footer">
          <div>{user?.is_demo ? "Demo account" : user?.email}</div>
          <button
            className="secondary"
            style={{ marginTop: 8 }}
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
      </nav>
      <main className="content">
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
    </div>
  );
}

const Loading = () => <div style={{ padding: 40 }}>Loading…</div>;

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
