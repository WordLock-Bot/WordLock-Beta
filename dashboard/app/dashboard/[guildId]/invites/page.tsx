"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { UserPlus, TrendingUp, Trophy, Medal } from "lucide-react";
import { api } from "@/lib/api";
import type { InvitesOverview } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { useI18n } from "@/lib/i18n";

export default function GuildInvites() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t, locale } = useI18n();
  const [data, setData] = useState<InvitesOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    api<InvitesOverview>(`/api/guilds/${guildId}/invites`)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [guildId]);

  if (loading) return <p className="text-gray-400">{t("common.loading")}</p>;
  if (error || !data)
    return <p className="text-gray-400">{t("common.unknownError")}</p>;

  const series = data.stats.series ?? [];
  const max = series.length ? Math.max(...series.map((p) => p.n), 1) : 1;
  const top = data.leaderboard[0];

  return (
    <div className="max-w-5xl space-y-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-bold text-white">
          <UserPlus className="h-7 w-7 text-blurple" /> {t("invites.title")}
        </h1>
        <p className="mt-1 text-sm text-gray-400">{t("invites.subtitle")}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label={t("invites.total")}
          value={data.stats.total.toLocaleString(locale)}
          icon={UserPlus}
          tone="default"
        />
        <StatCard
          label={t("invites.recent")}
          value={data.stats.recent.toLocaleString(locale)}
          icon={TrendingUp}
          tone="green"
        />
        <StatCard
          label={t("invites.topInviter")}
          value={top ? top.invites.toLocaleString(locale) : 0}
          icon={Trophy}
          tone="yellow"
        />
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("invites.seriesTitle")}</h2>
        {series.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">{t("common.noData")}</p>
        ) : (
          <>
            <div className="flex h-40 items-end gap-1">
              {series.map((p, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-t bg-blurple/60 transition hover:bg-blurple"
                  style={{ height: `${Math.max((p.n / max) * 100, 2)}%` }}
                  title={`${p.date}: ${p.n}`}
                />
              ))}
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-gray-500">
              <span>{series[0]?.date}</span>
              <span>{series[Math.floor(series.length / 2)]?.date}</span>
              <span>{series[series.length - 1]?.date}</span>
            </div>
          </>
        )}
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("invites.leaderboardTitle")}</h2>
        {data.leaderboard.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">{t("common.noData")}</p>
        ) : (
          <ul className="space-y-2">
            {data.leaderboard.map((entry, idx) => (
              <li
                key={String(entry.inviter_id)}
                className="flex items-center gap-3 rounded-lg bg-white/5 px-4 py-3"
              >
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-md text-xs font-bold ${
                    idx === 0
                      ? "bg-wordlock-yellow/20 text-wordlock-yellow"
                      : idx === 1
                        ? "bg-white/10 text-gray-300"
                        : idx === 2
                          ? "bg-amber-700/20 text-amber-400"
                          : "bg-white/5 text-gray-500"
                  }`}
                >
                  {idx < 3 ? <Medal className="h-4 w-4" /> : idx + 1}
                </span>
                <span className="font-mono text-sm text-gray-200">{String(entry.inviter_id)}</span>
                <span className="ml-auto text-sm font-semibold text-white">
                  {entry.invites.toLocaleString(locale)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
