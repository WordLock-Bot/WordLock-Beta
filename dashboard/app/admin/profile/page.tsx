"use client";

import { useEffect, useState } from "react";
import { ImagePlus, Save, RotateCcw, AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { BotProfile, ProfileHistoryEntry } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

function fileToDataUri(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("File read error"));
    reader.readAsDataURL(file);
  });
}

export default function AdminProfile() {
  const { t, locale } = useI18n();
  const [profile, setProfile] = useState<BotProfile | null>(null);
  const [history, setHistory] = useState<ProfileHistoryEntry[]>([]);
  const [avatar, setAvatar] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await api<{ profile: BotProfile | null; history: ProfileHistoryEntry[] }>(
      "/api/admin/profile",
    );
    setProfile(res.profile);
    setHistory(res.history ?? []);
    setAvatar(res.profile?.avatar ?? null);
  };

  useEffect(() => {
    load().catch((e: ApiError) => setError(e.message));
  }, []);

  const pick = async (file?: File) => {
    if (!file) return;
    const dataUri = await fileToDataUri(file);
    setAvatar(dataUri);
  };

  const apply = async () => {
    if (!avatar) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/admin/profile/apply", { method: "POST", body: JSON.stringify({ avatar }) });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const reset = async () => {
    if (!window.confirm(t("adProf.resetConfirm"))) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/admin/profile/reset", { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-5xl space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-white">{t("adProf.title")}</h1>
          <p className="mt-1 text-sm text-gray-400">{t("adProf.subtitle")}</p>
        </div>
        <button onClick={reset} disabled={busy} className="btn-danger">
          <RotateCcw className="h-4 w-4" />
          {t("adProf.reset")}
        </button>
      </header>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-wordlock-red/15 px-4 py-3 text-sm text-red-300">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adProf.current")}</h2>
          <div className="flex items-center gap-5">
            {avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatar}
                alt=""
                className="h-20 w-20 rounded-full border-2 border-white/10 object-cover"
              />
            ) : (
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-white/5 text-xs text-gray-500">
                {t("adProf.noImage")}
              </div>
            )}
            <label className="cursor-pointer rounded-lg bg-white/10 px-3 py-2 text-sm text-white hover:bg-white/20">
              <ImagePlus className="mr-1 inline h-4 w-4" />
              {t("adProf.replace")}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => pick(e.target.files?.[0])}
              />
            </label>
          </div>
          <button onClick={apply} disabled={busy || !avatar} className="btn-primary mt-5 w-full">
            <Save className="h-4 w-4" />
            {busy ? t("common.loading") : t("adProf.apply")}
          </button>
          <p className="mt-3 text-xs text-gray-500">
            {t("adProf.lastChangedBy", {
              by: profile?.updated_by ?? "–",
              date: profile?.updated_at ? new Date(profile.updated_at).toLocaleString(locale) : "–",
            })}
          </p>
        </div>

        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adProf.history")}</h2>
          {history.length === 0 ? (
            <p className="text-sm text-gray-500">{t("adProf.noChanges")}</p>
          ) : (
            <ul className="divide-y divide-white/5">
              {history.map((h) => (
                <li key={h.id} className="py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-white">{t("adProf.header")}</span>
                    <span className="text-xs text-gray-500">
                      {new Date(h.created_at).toLocaleString(locale)}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-gray-400">
                    {t("adProf.by")} <span className="text-gray-300">@{h.updated_by}</span>
                    {h.guild_id ? (
                      <>
                        {" "}
                        · {t("adProf.server")} <span className="text-gray-300">{h.guild_id}</span>
                      </>
                    ) : (
                      <span className="text-blurple"> · {t("adProf.adminPanel")}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
