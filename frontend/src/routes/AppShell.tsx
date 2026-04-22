import { Link, Outlet, useRouter } from "@tanstack/react-router";

import { endpoints } from "../api/client";
import { useAuth } from "../store/auth";
import { Button } from "../components/ui";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/controllers", label: "Controllers" },
  { to: "/blueprints", label: "Blueprints" },
  { to: "/fleets", label: "Fleets" },
  { to: "/devices", label: "Devices" },
  { to: "/firmware", label: "Firmware" },
];

export function AppShell() {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const clear = useAuth((s) => s.clear);

  const logout = async () => {
    try {
      const { refresh } = useAuth.getState();
      if (refresh) {
        await fetch("/api/v1/auth/jwt/blacklist/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
        });
      }
    } catch {
      // fine — we're clearing local state regardless
    }
    clear();
    router.navigate({ to: "/login", search: { redirect: undefined } });
  };

  // Opportunistically hydrate user
  if (!user) {
    endpoints
      .me()
      .then((u) => useAuth.getState().setUser(u))
      .catch(() => {
        /* ignore — unauthenticated; route guards handle redirect */
      });
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
          <Link to="/" className="text-sm font-semibold tracking-tight">
            UVL <span className="text-slate-500">· UniFi Virtual Lab</span>
          </Link>
          <nav className="flex gap-1">
            {NAV.map((n) => (
              <Link
                key={n.to}
                to={n.to}
                className="px-3 py-1.5 text-sm rounded-md text-slate-400 hover:text-white hover:bg-slate-800"
                activeProps={{ className: "text-white bg-slate-800" }}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {user && <span className="text-slate-400">{user.email}</span>}
            <Button variant="ghost" size="sm" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
