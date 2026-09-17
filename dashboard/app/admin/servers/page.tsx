"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Server, RefreshCw, UserX, Trash2, Link as LinkIcon, Copy, Check, Search, ArrowUpRight } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminServer } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const STATUS_TONES: Record<string, string> = {
  active: "bg-wordlock-green/15 text-wordlock-green",
  disabled: "bg-wordlock-red/15 text-wordlock-red",
  maintenance: "bg-wordlock-yellow/15 text-wordlock-yellow",
};

type InviteInfo = { url: string; channel: string | null; expires_at: string };

export default function AdminServers() {
  const { t, locale } = useI18n();
  const [servers, setServers] = useState<AdminServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [invites, setInvites] = useState<Record<string, InviteInfo>>({});
  const [copied, setCopied] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");

  const reload = () => {
    setLoading(true);
    api<AdminServer[]>("/api/admin/servers").then(setServers).finally(() => setLoading(false));
  };

  useEffect(reload, []);

  const filtered = servers.filter((s) => {
    if (filter !== "all" && s.status !== filter) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      (s.name || "").toLowerCase().includes(q) ||
      s.guild_id.includes(q)
    );
  });

  const loadInvites = async (list: AdminServer[]) => {
    const entries: [string, InviteInfo][] = [];
    for (const s of list) {
      try {
        const inv = await api<InviteInfo>(`/api/admin/servers/${s.guild_id}/invite`);
        entries.push([s.guild_id, inv]);
      } catch {
        // invite unavailable
      }
    }
    setInvites(Object.fromEntries(entries));
  };

  useEffect(() => {
    if (!loading && servers.length) loadInvites(servers);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, servers.length]);

  const setStatus = async (gid: string, status: string) => {
    try {
      await api(`/api/admin/servers/${gid}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      reload();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const toggleBypassPrivileged = async (s: AdminServer) => {
    try {
      await api(`/api/admin/servers/${s.guild_id}`, {
        method: "PATCH",
        body: JSON.stringify({ bypass_privileged: !s.bypass_privileged }),
      });
      reload();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const kickBot = async (s: AdminServer) => {
    if (!window.confirm(`${t("adServ.kickConfirm")} "${s.name || s.guild_id}"?`)) return;
    try {
      await api(`/api/admin/servers/${s.guild_id}/kick`, { method: "POST" });
      reload();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const forceRemove = async (s: AdminServer) => {
    if (!window.confirm(`${t("adServ.forceRemoveConfirm")} "${s.name || s.guild_id}"?`)) return;
    try {
      await api(`/api/admin/servers/${s.guild_id}/force-remove`, { method: "POST" });
      reload();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const refreshInvite = async (s: AdminServer) => {
    try {
      const res = await api<InviteInfo>(`/api/admin/servers/${s.guild_id}/invite`, {
        method: "POST",
      });
      setInvites((prev) => ({ ...prev, [s.guild_id]: res }));
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const copyInvite = async (s: AdminServer) => {
    const inv = invites[s.guild_id];
    if (!inv) return;
    await navigator.clipboard.writeText(inv.url);
    setCopied(s.guild_id);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">{t("adServ.title")}</h1>
          <p className="mt-1 text-sm text-gray-400">
            {t("adServ.subtitle", { count: String(servers.length) })}
          </p>
        </div>
        <button onClick={reload} className="btn-secondary">
          <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
        </button>
      </header>

      {loading ? (
        <p className="text-gray-400">{t("common.loading")}</p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative min-w-[220px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <input
                className="input pl-9"
                placeholder={t("adServ.searchPlaceholder")}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <select className="input w-auto" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">{t("adServ.filterAll")}</option>
              <option value="active">{t("adServ.filterActive")}</option>
              <option value="disabled">{t("adServ.filterDisabled")}</option>
              <option value="maintenance">{t("adServ.filterMaintenance")}</option>
            </select>
          </div>
          <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-gray-400">
                <th className="pb-2">{t("adServ.thServer")}</th>
                <th className="pb-2">{t("adServ.thId")}</th>
                <th className="pb-2">{t("adServ.thMembers")}</th>
                <th className="pb-2">{t("adServ.thVersion")}</th>
                <th className="pb-2">{t("adServ.thStatus")}</th>
                <th className="pb-2">{t("settings.bypassPrivileged")}</th>
                <th className="pb-2">{t("adServ.thInvite")}</th>
                <th className="pb-2 text-right">{t("adServ.thActions")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.guild_id} className="border-b border-white/5 last:border-0">
                  <td className="py-3">
                    <Link
                      href={`/admin/servers/${s.guild_id}`}
                      className="group flex items-center gap-2 font-medium text-white hover:text-blurple"
                    >
                      <Server className="h-4 w-4 text-blurple" /> {s.name || "—"}
                      <ArrowUpRight className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
                    </Link>
                  </td>
                  <td className="py-3 font-mono text-xs text-gray-400">{s.guild_id}</td>
                  <td className="py-3 text-gray-300">{s.member_count?.toLocaleString(locale)}</td>
                  <td className="py-3 font-mono text-xs text-gray-400">v{s.bot_version ?? "?"}</td>
                  <td className="py-3">
                    <span className={`badge ${STATUS_TONES[s.status] ?? "bg-white/5 text-gray-400"}`}>
                      {s.status}
                    </span>
                  </td>
                  <td className="py-3">
                    <button
                      onClick={() => toggleBypassPrivileged(s)}
                      className={`relative h-6 w-11 rounded-full transition ${
                        s.bypass_privileged ? "bg-wordlock-green" : "bg-white/10"
                      }`}
                      title={t("settings.bypassPrivilegedDesc")}
                      aria-label={t("settings.bypassPrivileged")}
                    >
                      <span
                        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${
                          s.bypass_privileged ? "left-[22px]" : "left-0.5"
                        }`}
                      />
                    </button>
                  </td>
                  <td className="py-3">
                    {invites[s.guild_id] ? (
                      <button
                        onClick={() => copyInvite(s)}
                        className="flex max-w-[220px] items-center gap-1.5 font-mono text-xs text-blurple hover:text-white"
                        title={invites[s.guild_id].url}
                      >
                        {copied === s.guild_id ? (
                          <Check className="h-3 w-3 shrink-0 text-wordlock-green" />
                        ) : (
                          <Copy className="h-3 w-3 shrink-0" />
                        )}
                        <span className="truncate">{invites[s.guild_id].url.replace(/^https?:\/\//, "")}</span>
                      </button>
                    ) : (
                      <span className="text-xs text-gray-500">—</span>
                    )}
                  </td>
                  <td className="py-3">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setStatus(s.guild_id, s.status === "active" ? "disabled" : "active")}
                        className="btn-secondary px-2 py-1 text-xs"
                      >
                        {s.status === "active" ? t("adServ.deactivate") : t("adServ.activate")}
                      </button>
                      <button
                        onClick={() => setStatus(s.guild_id, s.status === "maintenance" ? "active" : "maintenance")}
                        className="btn-secondary px-2 py-1 text-xs"
                      >
                        {t("adServ.maintenance")}
                      </button>
                      <button
                        onClick={() => refreshInvite(s)}
                        className="btn-secondary px-2 py-1 text-xs"
                        title={t("adServ.inviteNew")}
                      >
                        <LinkIcon className="h-3 w-3" /> {t("adServ.inviteNew")}
                      </button>
                      <button
                        onClick={() => kickBot(s)}
                        className="btn-danger px-2 py-1 text-xs"
                        title={t("adServ.kick")}
                      >
                        <UserX className="h-3 w-3" /> {t("adServ.kick")}
                      </button>
                      <button
                        onClick={() => forceRemove(s)}
                        className="btn-danger px-2 py-1 text-xs"
                        title={t("adServ.forceRemove")}
                      >
                        <Trash2 className="h-3 w-3" /> {t("adServ.forceRemove")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-500">{t("adServ.noResults")}</p>
          )}
          </div>
        </>
      )}
    </div>
  );
}
