"use client";

import { useEffect, useState } from "react";
import { History, Server, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import { useI18n } from "@/lib/i18n";

interface HistoryEntry {
  id: number;
  guild_id: string;
  name: string;
  joined_at: string;
  left_at: string | null;
}

interface HistoryData {
  total: number;
  active: number;
  entries: HistoryEntry[];
}

export default function AdminHistory() {
  const { t } = useI18n();
  const [data, setData] = useState<HistoryData | null>(null);

  useEffect(() => {
    api<HistoryData>("/api/admin/history/servers").then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <p className="text-gray-400">{t("admin.historyLoading")}</p>;

  const fmt = (d: string) =>
    new Date(d).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  const duration = (joined: string, left: string | null) => {
    const start = new Date(joined);
    const end = left ? new Date(left) : new Date();
    const ms = Math.max(0, end.getTime() - start.getTime());
    const days = Math.floor(ms / (1000 * 60 * 60 * 24));
    const hours = Math.floor((ms % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    if (days > 0) return `${days}d ${hours}h`;
    const mins = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("admin.history")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("admin.historySubtitle")}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label={t("admin.historyTotal")} value={data.total} icon={History} tone="default" />
        <StatCard label={t("admin.historyActive")} value={data.active} icon={Activity} tone="green" />
        <StatCard label={t("admin.historyTable")} value={data.entries.length} icon={Server} tone="default" />
      </div>

      <div className="card overflow-hidden">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("admin.historyTable")}</h2>
        {data.entries.length === 0 ? (
          <p className="py-8 text-center text-gray-500">{t("admin.historyEmpty")}</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-gray-400">
                <th className="pb-3 pr-3">{t("admin.historyName")}</th>
                <th className="pb-3 pr-3">{t("admin.historyGuildId")}</th>
                <th className="pb-3 pr-3">{t("admin.historyJoined")}</th>
                <th className="pb-3 pr-3">{t("admin.historyLeft")}</th>
                <th className="pb-3 pr-3">{t("admin.historyDuration")}</th>
                <th className="pb-3">{t("admin.historyStatus")}</th>
              </tr>
            </thead>
            <tbody>
              {data.entries.map((e) => (
                <tr key={e.id} className="border-b border-white/5 last:border-0">
                  <td className="py-3 pr-3 font-medium text-white">{e.name || "—"}</td>
                  <td className="py-3 pr-3 font-mono text-xs text-gray-400">{e.guild_id}</td>
                  <td className="py-3 pr-3 text-gray-400">{fmt(e.joined_at)}</td>
                  <td className="py-3 pr-3 text-gray-400">{e.left_at ? fmt(e.left_at) : "—"}</td>
                  <td className="py-3 pr-3 text-gray-400">{duration(e.joined_at, e.left_at)}</td>
                  <td className="py-3">
                    {e.left_at ? (
                      <span className="rounded-full bg-gray-500/15 px-2.5 py-0.5 text-xs font-medium text-gray-400">
                        {t("admin.historyLeftBadge")}
                      </span>
                    ) : (
                      <span className="rounded-full bg-wordlock-green/15 px-2.5 py-0.5 text-xs font-medium text-wordlock-green">
                        {t("admin.historyActiveBadge")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}