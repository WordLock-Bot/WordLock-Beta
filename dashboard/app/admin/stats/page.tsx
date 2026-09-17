"use client";

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";
import { api } from "@/lib/api";
import type { AdminStats } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { ViolationsChart, GrowthChart, TopWordsList } from "@/components/Charts";
import { useI18n } from "@/lib/i18n";

export default function AdminStats() {
  const { t } = useI18n();
  const [data, setData] = useState<AdminStats | null>(null);

  useEffect(() => {
    api<AdminStats>("/api/admin/stats").then(setData);
  }, []);

  if (!data) return <p className="text-gray-400">{t("adStats.loading")}</p>;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("adStats.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("adStats.subtitle")}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label={t("adStats.activeServers")} value={data.servers} icon={BarChart3} />
        <StatCard label={t("adStats.activeUsers")} value={data.active_users} icon={BarChart3} tone="green" />
        <StatCard label={t("adStats.totalViolations")} value={data.violations_total} icon={BarChart3} tone="yellow" />
        <StatCard label={t("adStats.filterWords")} value={data.top_words.length} icon={BarChart3} tone="red" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.perDay")}</h2>
          <ViolationsChart data={data.violations_series} />
        </div>
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.growth")}</h2>
          <GrowthChart data={data.server_growth} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.topWords")}</h2>
          <TopWordsList data={data.top_words} />
        </div>
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.actions")}</h2>
          <ul className="space-y-3">
            {data.action_counts.map((a) => (
              <li key={a.action} className="flex justify-between rounded-lg bg-white/5 px-4 py-2.5 text-sm">
                <span className="capitalize text-gray-200">{a.action}</span>
                <span className="font-semibold text-white">{a.count}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adStats.topServers")}</h2>
          <ul className="space-y-3">
            {data.per_guild.slice(0, 8).map((g) => (
              <li key={g.guild_id} className="flex justify-between rounded-lg bg-white/5 px-4 py-2.5 text-sm">
                <span className="font-mono text-xs text-gray-300">{g.guild_id}</span>
                <span className="font-semibold text-white">{g.count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
