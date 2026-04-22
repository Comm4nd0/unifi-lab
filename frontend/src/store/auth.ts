import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AuthUser = {
  id: string;
  email: string;
  is_admin: boolean;
};

type AuthState = {
  access: string | null;
  refresh: string | null;
  user: AuthUser | null;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: AuthUser | null) => void;
  clear: () => void;
};

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      access: null,
      refresh: null,
      user: null,
      setTokens: (access, refresh) => set({ access, refresh }),
      setUser: (user) => set({ user }),
      clear: () => set({ access: null, refresh: null, user: null }),
    }),
    {
      name: "uvl-auth",
      partialize: (s) => ({ access: s.access, refresh: s.refresh, user: s.user }),
    },
  ),
);
