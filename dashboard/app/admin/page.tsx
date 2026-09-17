"use client";

import { useEffect, useState } from "react";
import { Server, Users, AlertTriangle, Bug, Activity, Clock, Rocket, BellOff, BellRing, Database, Trash2, MessageSquare, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminOverview, AdminInvites, MonitorStatus, Me } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { useI18n } from "@/lib/i18n";

export default function AdminOverview() {
  const { t, locale } = useI18n();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [monitor, setMonitor] = useState<MonitorStatus | null>(null);
  const [invites, setInvites] = useState<AdminInvites | null>(null);
  const [muting, setMuting] = useState(false);
  const [role, setRole] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    api<AdminOverview>("/api/admin/overview").then(setData);
    api<AdminInvites>("/api/admin/invites").then(setInvites).catch(() => setInvites(null));
    api<MonitorStatus>("/api/admin/monitor").then(setMonitor).catch(() => setMonitor(null));
    api<Me>("/api/auth/me").then((me) => setRole(me.role)).catch(() => {});
  }, []);

  const toggleMute = async () => {
    if (!monitor) return;
    setMuting(true);
    try {
      const res = await api<{ muted: boolean }>("/api/admin/monitor/mute", {
        method: "POST",
        body: JSON.stringify({ muted: !monitor.muted }),
      });
      setMonitor((m) => (m ? { ...m, muted: res.muted } : m));
    } finally {
      setMuting(false);
    }
  };

  const resetDb = async () => {
    if (!window.confirm(t("adminOv.resetDbConfirm"))) return;
    setResetting(true);
    try {
      await api("/api/admin/db/reset", { method: "POST" });
      window.location.reload();
    } catch (e) {
      alert((e as Error).message);
      setResetting(false);
    }
  };

  if (!data) return <p className="text-gray-400">{t("adminOv.loading")}</p>;

  const statusDot = (s: string) => (
    <span className={`inline-block h-2.5 w-2.5 rounded-full ${s === "online" || s === "connected" ? "bg-wordlock-green" : "bg-wordlock-red"}`} />
  );

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{t("adminOv.title")}</h1>
          <p className="mt-1 text-sm text-gray-400">
            {t("adminOv.started", {
              version: data.version,
              date: data.started_at ? new Date(data.started_at).toLocaleString(locale) : "—",
            })}
          </p>
        </div>
        <div className="card flex items-center gap-3">
          <Activity className="h-5 w-5 text-blurple" />
          <div className="text-xs">
            <div className="flex items-center gap-1.5">
              {statusDot(data.status.bot)} {t("adminOv.bot")}: {data.status.bot}
            </div>
            <div className="flex items-center gap-1.5">
              {statusDot(data.status.api)} {t("adminOv.api")}: {data.status.api}
            </div>
            <div className="flex items-center gap-1.5">
              {statusDot(data.status.database)} {t("adminOv.database")}: {data.status.database}
            </div>
          </div>
        </div>
        {role === "owner" && (
          <button onClick={resetDb} disabled={resetting} className="btn-danger">
            {resetting ? (
              <Database className="h-4 w-4 animate-pulse" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            {t("adminOv.resetDb")}
          </button>
        )}
      </header>

      {data.maintenance_mode && (
        <div className="rounded-xl border border-wordlock-yellow/40 bg-wordlock-yellow/10 p-4 text-sm text-wordlock-yellow">
          {t("adminOv.maintenance")}
        </div>
      )}

      {monitor && (
        <div
          className={`rounded-xl border p-4 ${
            monitor.down
              ? "border-wordlock-red/40 bg-wordlock-red/10"
              : "border-wordlock-green/40 bg-wordlock-green/10"
          }`}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <BellRing className={`h-5 w-5 ${monitor.down ? "text-wordlock-red" : "text-wordlock-green"}`} />
              <div>
                <div className="flex items-center gap-2 font-semibold text-white">
                  {t("monitor.title")}
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      monitor.down ? "bg-wordlock-red/20 text-red-300" : "bg-wordlock-green/20 text-wordlock-green"
                    }`}
                  >
                    {monitor.down ? t("monitor.down") : t("monitor.ok")}
                  </span>
                </div>
                <div className="mt-0.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-300">
                  <span className={monitor.api_ok ? "text-wordlock-green" : "text-red-300"}>
                    {t("monitor.api")}: {monitor.api_ok ? "OK" : "DOWN"}
                  </span>
                  <span className={monitor.bot_ok ? "text-wordlock-green" : "text-red-300"}>
                    {t("monitor.bot")}: {monitor.bot_ok ? "OK" : "DOWN"}
                  </span>
                  {monitor.down_since && (
                    <span className="text-gray-400">
                      {t("monitor.downSince", {
                        date: new Date(monitor.down_since).toLocaleString(locale),
                      })}
                    </span>
                  )}
                  {monitor.muted && (
                    <span className="flex items-center gap-1 text-wordlock-yellow">
                      <BellOff className="h-3 w-3" /> {t("monitor.muted")}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={toggleMute}
              disabled={muting || !monitor.down}
              className={`btn-secondary ${!monitor.down ? "opacity-40" : ""}`}
            >
              {monitor.muted ? <BellRing className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
              {muting ? t("common.loading") : monitor.muted ? t("monitor.unmute") : t("monitor.mute")}
            </button>
          </div>
          {monitor.down && <p className="mt-2 text-xs text-gray-400">{t("monitor.muteDesc")}</p>}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("adminOv.servers")} value={data.servers} icon={Server} />
        <StatCard label={t("adminOv.activeUsers")} value={data.active_users} icon={Users} tone="green" />
        <StatCard label={t("adminOv.violationsToday")} value={data.violations_today} icon={AlertTriangle} tone="yellow" />
        <StatCard label={t("adminOv.errors")} value={data.error_count} icon={Bug} tone="red" />
        <StatCard icon={MessageSquare} label={t("adminOv.openTickets")} value={data.open_tickets ?? 0} tone="default" />
        <StatCard label={t("admin.invites")} value={invites?.total ?? 0} icon={UserPlus} tone="green" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Rocket className="h-5 w-5 text-blurple" /> {t("adminOv.lastUpdates")}
          </h2>
          {data.last_updates.length ? (
            <ul className="space-y-3">
              {data.last_updates.map((u) => (
                <li key={u.id} className="rounded-lg bg-white/5 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white">{u.version}</span>
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <Clock className="h-3 w-3" />
                      {new Date(u.date).toLocaleDateString(locale)}
                    </span>
                  </div>
                  <div className="text-sm text-gray-300">{u.title}</div>
                  {u.changelog && (
                    <p className="mt-1 whitespace-pre-line text-xs text-gray-500">{u.changelog}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-gray-500">{t("adminOv.noUpdates")}</p>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adminOv.metrics")}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-white/5 p-4">
              <div className="text-2xl font-bold text-white">{data.servers}</div>
              <div className="text-xs text-gray-400">{t("adminOv.totalServers")}</div>
            </div>
            <div className="rounded-lg bg-white/5 p-4">
              <div className="text-2xl font-bold text-white">{data.active_servers}</div>
              <div className="text-xs text-gray-400">{t("adminOv.activeServers")}</div>
            </div>
            <div className="rounded-lg bg-white/5 p-4">
              <div className="text-2xl font-bold text-white">{data.violations_total}</div>
              <div className="text-xs text-gray-400">{t("adminOv.totalViolations")}</div>
            </div>
            <div className="rounded-lg bg-white/5 p-4">
              <div className="text-2xl font-bold text-white">{data.error_count}</div>
              <div className="text-xs text-gray-400">{t("adminOv.errorLogs")}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
