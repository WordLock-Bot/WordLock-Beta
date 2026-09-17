"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Shield, Plus, Loader2, Users, ShieldCheck, Ban } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { BackendStatus } from "@/components/BackendStatus";

const ADMIN_ROLES = ["owner", "developer", "moderator"];

const INVITE_URL =
  process.env.NEXT_PUBLIC_INVITE_URL ||
  "https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=328566625280&scope=bot%20applications.commands";

function guildIcon(guild: Me["admin_guilds"][number], size = 128) {
  if (!guild.icon) return null;
  const ext = guild.icon.startsWith("a_") ? "gif" : "png";
  return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.${ext}?size=${size}`;
}

export default function DashboardHome() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const [me, setMe] = useState<Me | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string>(INVITE_URL);
  const [loading, setLoading] = useState(true);
  const [adminChecking, setAdminChecking] = useState(false);
  const [adminDenied, setAdminDenied] = useState(false);

  useEffect(() => {
    Promise.all([
      api<Me>("/api/auth/me"),
      api<{ url: string }>("/api/auth/invite").catch(() => null),
    ])
      .then(([data, invite]) => {
        setMe(data);
        if (invite?.url) setInviteUrl(invite.url);
      })
      .catch((e: ApiError) => {
        if (e.status === 401) router.replace("/");
      })
      .finally(() => setLoading(false));
  }, [router]);

  const openAdmin = async () => {
    if (adminChecking) return;
    setAdminChecking(true);
    setAdminDenied(false);
    try {
      const meData = await api<Me>("/api/auth/me");
      if (ADMIN_ROLES.includes(meData.role)) {
        router.push("/admin");
      } else {
        setAdminDenied(true);
      }
    } catch {
      setAdminDenied(true);
    } finally {
      setAdminChecking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blurple" />
      </div>
    );
  }

  if (!me) return null;

  const installed = me.admin_guilds.filter((g) => g.bot_in_server);
  const missing = me.admin_guilds.filter((g) => !g.bot_in_server);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-10 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">{t("dash.chooseServer")}</h1>
          <p className="mt-2 text-gray-400">
            {t("dash.loggedInAs", { name: me.username })}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <button
            onClick={openAdmin}
            className="btn-primary"
            disabled={adminChecking}
          >
            {adminChecking ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
            {t("dash.adminPanel")}
          </button>
          {adminDenied && (
            <div className="flex items-center gap-1.5 text-xs text-wordlock-red">
              <Ban className="h-3 w-3" /> {t("dash.adminDenied")}
            </div>
          )}
        </div>
      </header>

      {me.maintenance && (
        <div className="mb-6 rounded-xl border border-wordlock-yellow/40 bg-wordlock-yellow/10 p-4 text-sm text-wordlock-yellow">
          {t("dash.maintenance")}
        </div>
      )}

      <div className="mb-6">
        <BackendStatus />
      </div>

      {me.admin_guilds.length === 0 && (
        <div className="card text-center text-gray-400">{t("dash.noServers")}</div>
      )}

      <section>
        <h2 className="mb-4 text-lg font-semibold text-white">
          {t("dash.connected", { count: installed.length })}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {installed.map((g) => (
            <Link key={g.id} href={`/dashboard/${g.id}`}>
              <div className="card group cursor-pointer transition hover:border-blurple/50 hover:bg-blurple/5">
                <div className="flex items-center gap-3">
                  {guildIcon(g) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={guildIcon(g) as string}
                      alt=""
                      className="h-12 w-12 rounded-full"
                    />
                  ) : (
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blurple/20 text-blurple">
                      <Shield className="h-6 w-6" />
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-white">{g.name}</div>
                    <div className="flex items-center gap-1 text-xs text-gray-400">
                      <Users className="h-3 w-3" /> {g.member_count.toLocaleString(locale)}
                    </div>
                    {!g.bot_has_admin && (
                      <div className="mt-1.5 flex items-center gap-1.5 rounded-md bg-wordlock-yellow/10 px-2 py-1 text-xs text-wordlock-yellow">
                        <Ban className="h-3 w-3 shrink-0" /> {t("dash.missingAdminPerm")}
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-3 text-xs text-blurple group-hover:underline">
                  {t("dash.openDashboard")}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="mb-4 text-lg font-semibold text-white">
          {t("dash.notInstalled", { count: missing.length })}
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {missing.map((g) => (
            <div key={g.id} className="card">
              <div className="flex items-center gap-3">
                {guildIcon(g) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={guildIcon(g) as string}
                    alt=""
                    className="h-12 w-12 rounded-full"
                  />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-gray-400">
                    <Shield className="h-6 w-6" />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="truncate font-semibold text-white">{g.name}</div>
                  <div className="flex items-center gap-1 text-xs text-gray-400">
                    <Users className="h-3 w-3" /> {g.member_count.toLocaleString(locale)}
                  </div>
                </div>
              </div>
              <a href={inviteUrl} target="_blank" rel="noreferrer" className="btn-primary mt-4 w-full">
                <Plus className="h-4 w-4" /> {t("dash.inviteBot")}
              </a>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
