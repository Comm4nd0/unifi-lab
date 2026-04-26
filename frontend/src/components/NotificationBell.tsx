import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { useChannel } from "../api/ws";
import { useToast } from "./toast";

type Notification = {
  id: string;
  title: string;
  message: string;
  level: "info" | "success" | "warning" | "error";
  target_type: string;
  target_id: string;
  read: boolean;
  created_at: string;
};

const LEVEL_COLORS: Record<string, string> = {
  info: "bg-blue-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  error: "bg-rose-500",
};

const TARGET_ROUTES: Record<string, string> = {
  fleet: "/fleets",
  controller: "/controllers",
  device: "/devices",
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const toast = useToast();

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: endpoints.notifications.list,
    refetchInterval: 30_000,
  });

  const markAllRead = useMutation({
    mutationFn: endpoints.notifications.markAllRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const dismiss = useMutation({
    mutationFn: (id: string) => endpoints.notifications.dismiss(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  // Subscribe to cluster WS for real-time notifications
  const { messages } = useChannel({ path: "/ws/cluster/" });
  const lastProcessed = useRef(0);

  useEffect(() => {
    if (messages.length <= lastProcessed.current) return;
    const newMsgs = messages.slice(lastProcessed.current);
    lastProcessed.current = messages.length;

    for (const msg of newMsgs) {
      if (msg.type === "notification.created" && msg.data) {
        const n = msg.data as unknown as Notification;
        // Show a toast for new notifications
        if (n.level === "error") {
          toast.error(n.title);
        } else if (n.level === "warning") {
          toast.error(n.title);  // toast.error for visibility, or use toast.success
        } else if (n.level === "success") {
          toast.success(n.title);
        } else {
          toast.success(n.title);
        }
        // Refetch the notification list
        qc.invalidateQueries({ queryKey: ["notifications"] });
      }
    }
  }, [messages.length, messages, qc, toast]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const notifications: Notification[] = data?.notifications ?? [];
  const unreadCount = data?.unread_count ?? 0;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="relative rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
        title="Notifications"
      >
        {/* Bell SVG icon */}
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 overflow-hidden rounded-lg border border-slate-800 bg-slate-950 shadow-xl z-50">
          <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
            <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Notifications
            </h3>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                className="text-[10px] text-indigo-400 hover:text-indigo-300"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-slate-500">
                No notifications
              </p>
            ) : (
              <ul className="divide-y divide-slate-800/50">
                {notifications.slice(0, 20).map((n) => (
                  <li
                    key={n.id}
                    className={
                      "group flex items-start gap-2.5 px-3 py-2.5 transition " +
                      (n.read ? "opacity-60" : "bg-slate-900/30")
                    }
                  >
                    <span
                      className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${
                        LEVEL_COLORS[n.level] ?? "bg-slate-500"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        {n.target_type && n.target_id ? (
                          <Link
                            to={`${TARGET_ROUTES[n.target_type] || ""}/${n.target_id}` as any}
                            onClick={() => setOpen(false)}
                            className="text-xs font-medium text-slate-200 hover:text-white"
                          >
                            {n.title}
                          </Link>
                        ) : (
                          <span className="text-xs font-medium text-slate-200">
                            {n.title}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => dismiss.mutate(n.id)}
                          className="flex-shrink-0 text-slate-600 opacity-0 group-hover:opacity-100 transition"
                          title="Dismiss"
                        >
                          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                      {n.message && (
                        <p className="mt-0.5 text-[11px] text-slate-500 line-clamp-2">
                          {n.message}
                        </p>
                      )}
                      <p className="mt-0.5 text-[10px] text-slate-600">
                        {timeAgo(n.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
