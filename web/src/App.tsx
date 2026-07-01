import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useStore } from "./store";
import Login from "./pages/Login";
import Teams from "./pages/Teams";
import Upload from "./pages/Upload";
import Tendencies from "./pages/Tendencies";
import Predict from "./pages/Predict";
import Vocabulary from "./pages/Vocabulary";

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

function Shell() {
  const { user, logout } = useStore();
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
          <div>{user?.email}</div>
          <button className="secondary" style={{ marginTop: 8 }} onClick={logout}>
            Sign out
          </button>
        </div>
      </nav>
      <main className="content">
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

export default function App() {
  const { user, loading } = useStore();
  if (loading) return <div style={{ padding: 40 }}>Loading…</div>;
  if (!user) return <Login />;
  return <Shell />;
}
