"use client";

import { useEffect, useState } from "react";
import { ShieldAlert, Power, CheckCircle2, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Incident } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export default function AdminIncidents() {
  const { t, locale } = useI18n();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true);
    setToast(null);
    try {
      setIncidents(await api<Incident[]>("/api/security/incidents"));
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resolve = async (id: number) => {
    if (!window.confirm(t("security.resolveConfirm"))) return;
    try {
      await api(`/api/security/incidents/${id}/resolve`, { method: "POST" });
      reload();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const reEnable = async (guildId: string) => {
    if (!window.confirm(t("security.reEnableConfirm"))) return;
    try {
      const res = await api<{ ok: boolean }>(`/api/security/guilds/${guildId}/enable`, {
        method: "POST",
      });
      setToast(t("security.enabledToast"));
      reload();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold text-white">
            <ShieldAlert className="h-7 w-7 text-wordlock-red" /> {t("security.title")}
          </h1>
          <p className="mt-1 text-sm text-gray-400">{t("security.subtitle")}</p>
        </div>
        <button onClick={reload} className="btn-secondary">
          <RefreshCw className="h-4 w-4" /> {t("common.refresh")}
        </button>
      </header>

      {toast && (
        <div className="rounded-lg bg-blurple/10 px-4 py-3 text-sm text-blurple">{toast}</div>
      )}

      {loading ? (
        <p className="text-gray-400">{t("common.loading")}</p>
      ) : incidents.length === 0 ? (
        <p className="py-10 text-center text-sm text-gray-500">{t("security.noIncidents")}</p>
      ) : (
        <div className="space-y-4">
          {incidents.map((inc) => (
            <div key={inc.id} className="card">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`badge ${
                    inc.status === "open"
                      ? "bg-wordlock-red/15 text-wordlock-red"
                      : "bg-wordlock-green/15 text-wordlock-green"
                  }`}
                >
                  {inc.status === "open" ? t("security.open") : t("security.resolved")}
                </span>
                <span className="font-semibold text-white">
                  {t(`security.kind.${inc.kind}`) === `security.kind.${inc.kind}`
                    ? inc.kind
                    : t(`security.kind.${inc.kind}`)}
                </span>
                <span className="text-xs text-gray-400">
                  {t("security.guild")}: {inc.guild_name ?? inc.guild_id}
                </span>
                <span className="ml-auto text-xs text-gray-500">
                  #{inc.id} • {new Date(inc.created_at).toLocaleString(locale)}
                </span>
              </div>
              <div className="mt-3 grid gap-2 text-sm text-gray-300 lg:grid-cols-2">
                {inc.actor_id != null && (
                  <div>
                    {t("security.actor")}:{" "}
                    <span className="font-mono text-xs">{inc.actor_id}</span>
                  </div>
                )}
                {inc.detail && Object.keys(inc.detail).length > 0 && (
                  <div>
                    {t("security.detail")}:{" "}
                    <span className="text-gray-400">
                      {Object.entries(inc.detail)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" · ")}
                    </span>
                  </div>
                )}
              </div>
              <div className="mt-2 text-xs text-gray-400">
                <span className="text-gray-500">{t("security.consequence")}:</span>{" "}
                {inc.consequence}
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => resolve(inc.id)}
                  disabled={inc.status !== "open"}
                  className="btn-secondary px-3 py-1.5 text-xs"
                >
                  <CheckCircle2 className="h-4 w-4" /> {t("security.resolve")}
                </button>
                <button
                  onClick={() => reEnable(inc.guild_id)}
                  className="btn-primary px-3 py-1.5 text-xs"
                >
                  <Power className="h-4 w-4" /> {t("security.reEnable")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
