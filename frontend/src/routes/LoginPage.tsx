import { FormEvent, useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";

import { ApiError, endpoints } from "../api/client";
import { useAuth } from "../store/auth";
import { Button, Card, Input, Label } from "../components/ui";

export function LoginPage() {
  const navigate = useNavigate();
  const search = useSearch({ strict: false }) as { redirect?: string };
  const setTokens = useAuth((s) => s.setTokens);
  const setUser = useAuth((s) => s.setUser);

  const [email, setEmail] = useState("admin@uvl.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { access, refresh } = await endpoints.jwtCreate(email, password);
      setTokens(access, refresh);
      const user = await endpoints.me();
      setUser(user);
      navigate({ to: search.redirect ?? "/" });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || "Invalid credentials");
      } else {
        setError((err as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold tracking-tight">UVL sign in</h1>
        <p className="mt-1 text-sm text-slate-400">
          Default dev account: <span className="font-mono">admin@uvl.local</span>
        </p>
        <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </main>
  );
}
