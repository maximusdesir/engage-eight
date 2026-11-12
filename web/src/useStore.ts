// Store context and hook. The provider lives in store.tsx; keeping these in a
// separate non-component module lets React fast refresh work on the provider.
import { createContext, useContext } from "react";
import type { Team, User } from "./api/client";

export type Store = {
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

export const Ctx = createContext<Store | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore must be used within StoreProvider");
  return s;
}
