// App-wide state: the logged-in user and the "active team" (drives the team_id
// used for vocabulary mapping and the offense_team filter used across screens).
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken, type Team, type User } from "./api/client";

const TEAM_KEY = "engage8_active_team_id";

type Store = {
  user: User | null;
  loading: boolean;
  teams: Team[];
  activeTeam: Team | null;
  setActiveTeam: (t: Team | null) => void;
  refreshTeams: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeamId, setActiveTeamId] = useState<number | null>(() => {
    const raw = localStorage.getItem(TEAM_KEY);
    return raw ? Number(raw) : null;
  });

  const refreshTeams = async () => {
    const t = await api.listTeams();
    setTeams(t);
    // Keep an active team selected if possible.
    setActiveTeamId((cur) =>
      cur && t.some((x) => x.id === cur) ? cur : t[0]?.id ?? null
    );
  };

  // On mount, if we have a token, load the user + teams.
  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          setUser(await api.me());
          await refreshTeams();
        } catch {
          setToken(null);
        }
      }
      setLoading(false);
    })();
  }, []);

  useEffect(() => {
    if (activeTeamId != null) localStorage.setItem(TEAM_KEY, String(activeTeamId));
    else localStorage.removeItem(TEAM_KEY);
  }, [activeTeamId]);

  const login = async (email: string, password: string) => {
    await api.login(email, password);
    setUser(await api.me());
    await refreshTeams();
  };
  const signup = async (email: string, password: string) => {
    await api.signup(email, password);
    await login(email, password);
  };
  const logout = () => {
    setToken(null);
    setUser(null);
    setTeams([]);
    setActiveTeamId(null);
  };

  const activeTeam = useMemo(
    () => teams.find((t) => t.id === activeTeamId) ?? null,
    [teams, activeTeamId]
  );

  const value: Store = {
    user,
    loading,
    teams,
    activeTeam,
    setActiveTeam: (t) => setActiveTeamId(t?.id ?? null),
    refreshTeams,
    login,
    signup,
    logout,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore must be used within StoreProvider");
  return s;
}
