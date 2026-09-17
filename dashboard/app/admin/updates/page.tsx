"use client";

import { useEffect, useState } from "react";
import { Rocket, History, Send } from "lucide-react";
import { api } from "@/lib/api";
import type { Update } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

export default function AdminUpdates() {
  const { t, locale } = useI18n();
  const [updates, setUpdates] = useState<Update[]>([]);
  const [form, setForm] = useState({
    version: "1.1.0",
    title: "",
    changelog: "",
    maintenance_mode: false,
  });
  const [releaseMsg, setReleaseMsg] = useState<string | null>(null);

  const reload = () => api<Update[]>("/api/admin/updates").then(setUpdates);
  useEffect(() => {
    reload();
  }, []);

  const publish = async (release: boolean) => {
    setReleaseMsg(null);
    try {
      const res = await api<any>(release ? "/api/admin/updates/release" : "/api/admin/updates", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setReleaseMsg(
        release
          ? t("adUpd.released", { version: res.version, deploy: res.deploy ?? "n/a" })
          : t("adUpd.announced", { version: res.version }),
      );
      if (release) {
        setForm({ ...form, changelog: "", title: "" });
      }
      reload();
    } catch (e) {
      setReleaseMsg((e as Error).message);
    }
  };

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("adUpd.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("adUpd.subtitle")}</p>
      </header>

      {releaseMsg && (
        <div className="rounded-lg bg-blurple/10 px-4 py-3 text-sm text-blurple">{releaseMsg}</div>
      )}

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-white">{t("adUpd.new")}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">{t("adUpd.version")}</label>
            <input
              className="input"
              value={form.version}
              onChange={(e) => setForm({ ...form, version: e.target.value })}
            />
          </div>
          <div>
            <label className="label">{t("adUpd.titleLabel")}</label>
            <input
              className="input"
              value={form.title}
              placeholder={t("adUpd.titlePlaceholder")}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label">{t("adUpd.changelog")}</label>
            <textarea
              className="input min-h-[120px]"
              value={form.changelog}
              placeholder={t("adUpd.changelogPlaceholder")}
              onChange={(e) => setForm({ ...form, changelog: e.target.value })}
            />
          </div>
          <div className="flex items-center gap-3">
            <input
              id="maintenance"
              type="checkbox"
              checked={form.maintenance_mode}
              onChange={(e) => setForm({ ...form, maintenance_mode: e.target.checked })}
              className="h-4 w-4 accent-blurple"
            />
            <label htmlFor="maintenance" className="text-sm text-gray-300">
              {t("adUpd.maintenance")}
            </label>
          </div>
        </div>
        <div className="mt-6 flex gap-3">
          <button onClick={() => publish(false)} className="btn-secondary">
            <Send className="h-4 w-4" /> {t("adUpd.announce")}
          </button>
          <button onClick={() => publish(true)} className="btn-primary">
            <Rocket className="h-4 w-4" /> {t("adUpd.release")}
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
          <History className="h-5 w-5 text-blurple" /> {t("adUpd.history")}
        </h2>
        {updates.length ? (
          <ul className="space-y-3">
            {updates.map((u) => (
              <li key={u.id} className="rounded-lg bg-white/5 px-4 py-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">{u.version}</span>
                  <div className="flex items-center gap-2">
                    {u.maintenance_mode && (
                      <span className="badge bg-wordlock-yellow/15 text-wordlock-yellow">
                        {t("adUpd.maintenanceBadge")}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {new Date(u.date).toLocaleString(locale)}
                    </span>
                  </div>
                </div>
                <div className="text-sm text-gray-300">{u.title}</div>
                {u.changelog && (
                  <pre className="mt-2 whitespace-pre-line rounded-lg bg-discord-dark p-3 font-mono text-xs text-gray-400">
                    {u.changelog}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-6 text-center text-sm text-gray-500">{t("adUpd.none")}</p>
        )}
      </div>
    </div>
  );
}
