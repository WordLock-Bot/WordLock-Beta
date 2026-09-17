"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Users, AlertTriangle, ShieldAlert, Activity, Power } from "lucide-react";
import { api } from "@/lib/api";
import type { ServerConfig, GuildStats } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { ViolationsChart, TopWordsList } from "@/components/Charts";
import { useI18n } from "@/lib/i18n";

export default function GuildOverview() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t, locale } = useI18n();
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [stats, setStats] = useState<GuildStats | null>(null);

  const load = () => {
    api<ServerConfig>(`/api/guilds/${guildId}`).then(setConfig).catch(() => setConfig(null));
    api<GuildStats>(`/api/guilds/${guildId}/stats`).then(setStats).catch(() => setStats(null));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId]);

  const reEnable = async () => {
    if (!window.confirm(t("security.reEnableConfirm"))) return;
    try {
      await api(`/api/guilds/${guildId}/enable`, { method: "POST" });
      load();
    } catch {
      /* keep state */
    }
  };

  if (!config || !stats) {
    return <p className="text-gray-400">{t("overview.loading")}</p>;
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{config.name}</h1>
        <p className="mt-1 text-sm text-gray-400">
          {t("overview.serverIdLine", {
            id: config.guild_id,
            status: config.status,
            version: config.bot_version ?? "?",
          })}
        </p>
      </header>

      {config.status === "disabled" && (
        <div className="rounded-xl border border-wordlock-red/40 bg-wordlock-red/10 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-wordlock-red">{t("security.disabledBanner")}</p>
            <button onClick={reEnable} className="btn-primary !bg-wordlock-green">
              <Power className="h-4 w-4" /> {t("security.reEnable")}
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("common.members")}
          value={stats.member_count.toLocaleString(locale)}
          icon={Users}
        />
        <StatCard
          label={t("overview.violationsToday")}
          value={stats.violations_today}
          icon={AlertTriangle}
          tone="yellow"
        />
        <StatCard
          label={t("overview.warnings")}
          value={stats.warning_count}
          icon={ShieldAlert}
          tone="red"
        />
        <StatCard
          label={t("overview.detectedWords")}
          value={stats.top_words.length}
          icon={Activity}
        />
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("overview.violations30")}</h2>
        <ViolationsChart data={stats.violations_series} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("overview.topWords")}</h2>
          <TopWordsList data={stats.top_words} />
        </div>
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("overview.actions")}</h2>
          {stats.actions.length ? (
            <ul className="space-y-3">
              {stats.actions.map((a) => (
                <li
                  key={a.action}
                  className="flex items-center justify-between rounded-lg bg-white/5 px-4 py-3 text-sm"
                >
                  <span className="capitalize text-gray-200">{a.action}</span>
                  <span className="font-semibold text-white">{a.count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-8 text-center text-sm text-gray-500">{t("overview.noActions")}</p>
          )}
        </div>
      </div>
    </div>
  );
}
