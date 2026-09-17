"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ShieldAlert, Power, Link2, Save } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Incident, ServerConfig } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export default function GuildSecurity() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t, locale } = useI18n();
  const [config, setConfig] = useState<ServerConfig | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = async () => {
    try {
      setConfig(await api<ServerConfig>(`/api/guilds/${guildId}`));
      setIncidents(await api<Incident[]>(`/api/guilds/${guildId}/incidents`));
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId]);

  const reEnable = async () => {
    if (!window.confirm(t("security.reEnableConfirm"))) return;
    try {
      const res = await api<{ ok: boolean; status: string }>(
        `/api/guilds/${guildId}/enable`,
        { method: "POST" },
      );
      setToast(t("security.enabledToast"));
      await load();
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  const savePhishing = async () => {
    if (!config) return;
    setSaved(false);
    try {
      await api(`/api/guilds/${guildId}`, {
        method: "PUT",
        body: JSON.stringify({
          phishing_enabled: config.phishing_enabled,
          phishing_action: config.phishing_action,
        }),
      });
      setToast(t("common.saved"));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setToast(e instanceof ApiError ? e.message : t("common.unknownError"));
    }
  };

  return (
    <div className="max-w-4xl space-y-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-bold text-white">
          <ShieldAlert className="h-7 w-7 text-wordlock-red" /> {t("security.title")}
        </h1>
        <p className="mt-1 text-sm text-gray-400">{t("security.subtitle")}</p>
      </header>

      {toast && (
        <div className="rounded-lg bg-blurple/10 px-4 py-3 text-sm text-blurple">{toast}</div>
      )}

      {config?.status === "disabled" && (
        <div className="rounded-xl border border-wordlock-red/40 bg-wordlock-red/10 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="font-semibold text-wordlock-red">
                🛡️ {t("security.disabledBanner")}
              </div>
            </div>
            <button onClick={reEnable} className="btn-primary !bg-wordlock-green">
              <Power className="h-4 w-4" /> {t("security.reEnable")}
            </button>
          </div>
        </div>
      )}

      <div className="card space-y-4">
        <h2 className="text-lg font-semibold text-white">
          {t("security.title")} ({incidents.length})
        </h2>
        {incidents.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">{t("security.noIncidents")}</p>
        ) : (
          incidents.map((inc) => (
            <div key={inc.id} className="rounded-lg bg-white/5 p-4">
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
                <span className="ml-auto text-xs text-gray-500">
                  {new Date(inc.created_at).toLocaleString(locale)}
                </span>
              </div>
              <div className="mt-2 grid gap-1 text-sm text-gray-300 sm:grid-cols-2">
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
            </div>
          ))
        )}
      </div>

      {config && (
        <div className="card">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
                <Link2 className="h-5 w-5 text-blurple" /> {t("security.phishingTitle")}
              </h2>
              <p className="mt-1 text-sm text-gray-400">{t("security.phishingDesc")}</p>
            </div>
            <button
              onClick={() =>
                setConfig({ ...config, phishing_enabled: !config.phishing_enabled })
              }
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold ${
                config.phishing_enabled
                  ? "bg-wordlock-green/20 text-wordlock-green"
                  : "bg-white/10 text-gray-300"
              }`}
            >
              <ShieldAlert className="h-4 w-4" />
              {config.phishing_enabled ? t("common.disable") : t("common.enable")}
            </button>
          </div>
          {config.phishing_enabled ? (
            <div className="space-y-4">
              <div>
                <label className="label">{t("security.phishAction")}</label>
                <select
                  className="input"
                  value={config.phishing_action}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      phishing_action: e.target.value as typeof config.phishing_action,
                    })
                  }
                >
                  <option value="delete">{t("security.phishAction.delete")}</option>
                  <option value="warn">{t("security.phishAction.warn")}</option>
                  <option value="timeout">{t("security.phishAction.timeout")}</option>
                  <option value="log">{t("security.phishAction.log")}</option>
                </select>
              </div>
              <p className="text-xs text-gray-500">{t("security.phishingNote")}</p>
            </div>
          ) : (
            <p className="py-2 text-sm text-gray-500">{t("common.disabled")}</p>
          )}
          <div className="mt-4 flex justify-end">
            <button onClick={savePhishing} className="btn-primary">
              <Save className="h-4 w-4" />
              {saved ? t("common.saved") : t("common.save")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
