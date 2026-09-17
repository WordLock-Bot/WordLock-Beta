"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Save, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface ChannelOption {
  id: string;
  name: string;
  type: number;
}

interface RoleOption {
  id: string;
  name: string;
  color: number;
  managed: boolean;
  position: number;
}

interface TicketConfig {
  guild_id: string;
  enabled: boolean;
  panel_channel_id: string | null;
  panel_message_id: string | null;
  category_id: string | null;
  welcome_message: string;
  ticket_name_format: string;
  support_role_ids: string[];
  max_open: number;
  panel_needs_deploy: boolean;
}

export default function TicketSetup() {
  const params = useParams();
  const guildId = (params?.guildId as string) ?? "";
  const { t } = useI18n();
  const [cfg, setCfg] = useState<TicketConfig | null>(null);
  const [channels, setChannels] = useState<ChannelOption[]>([]);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [saved, setSaved] = useState(false);
  const [deployQueued, setDeployQueued] = useState(false);

  useEffect(() => {
    api<TicketConfig>(`/api/guilds/${guildId}/ticket-config`).then(setCfg);
    api<{ channels: ChannelOption[] }>(`/api/guilds/${guildId}/channels`)
      .then((r) => setChannels(r.channels ?? []))
      .catch(() => setChannels([]));
    api<{ roles: RoleOption[] }>(`/api/guilds/${guildId}/roles`)
      .then((r) => setRoles(r.roles ?? []))
      .catch(() => setRoles([]));
  }, [guildId]);

  const save = async () => {
    if (!cfg) return;
    setSaved(false);
    setDeployQueued(false);
    await api(`/api/guilds/${guildId}/ticket-config`, {
      method: "PUT",
      body: JSON.stringify({
        panel_channel_id: cfg.panel_channel_id ? Number(cfg.panel_channel_id) : null,
        category_id: cfg.category_id ? Number(cfg.category_id) : null,
        support_role_ids: cfg.support_role_ids.map(Number),
        max_open: cfg.max_open,
        welcome_message: cfg.welcome_message,
        ticket_name_format: cfg.ticket_name_format,
      }),
    });
    setSaved(true);
    setDeployQueued(true);
    setTimeout(() => setSaved(false), 2000);
    setTimeout(() => setDeployQueued(false), 5000);
  };

  const toggleRole = (roleId: string) => {
    if (!cfg) return;
    const current = cfg.support_role_ids;
    const next = current.includes(roleId)
      ? current.filter((r) => r !== roleId)
      : [...current, roleId];
    setCfg({ ...cfg, support_role_ids: next });
  };

  if (!cfg) return <p className="text-gray-400">{t("ticketsetup.loading")}</p>;

  const textChannels = channels.filter((c) => c.type === 0);
  const categories = channels.filter((c) => c.type === 4);

  return (
    <div className="max-w-5xl space-y-8">
      <header>
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold text-white">{t("ticketsetup.title")}</h1>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              cfg.enabled
                ? "bg-wordlock-green/20 text-wordlock-green"
                : "bg-white/10 text-gray-400"
            }`}
          >
            {cfg.enabled ? t("ticketsetup.enabled") : t("ticketsetup.disabled")}
          </span>
        </div>
        <p className="mt-1 text-sm text-gray-400">{t("ticketsetup.subtitle")}</p>
        <Link
          href={`/server/${guildId}/tickets`}
          className="mt-4 inline-flex items-center gap-2 text-sm text-blurple hover:text-blurple/80"
        >
          <ExternalLink className="h-4 w-4" /> {t("ticketsetup.viewLive")}
        </Link>
      </header>

      <div className="card space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">{t("ticketsetup.panelChannel")}</label>
            <select
              className="input"
              value={cfg.panel_channel_id ?? ""}
              onChange={(e) =>
                setCfg({ ...cfg, panel_channel_id: e.target.value || null })
              }
            >
              <option value="">{t("ticketsetup.panelChannelNone")}</option>
              {textChannels.map((c) => (
                <option key={c.id} value={c.id}>
                  # {c.name}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">{t("ticketsetup.panelChannelDesc")}</p>
          </div>
          <div>
            <label className="label">{t("ticketsetup.category")}</label>
            <select
              className="input"
              value={cfg.category_id ?? ""}
              onChange={(e) =>
                setCfg({ ...cfg, category_id: e.target.value || null })
              }
            >
              <option value="">{t("ticketsetup.categoryNone")}</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  📁 {c.name}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">{t("ticketsetup.categoryDesc")}</p>
          </div>
          <div>
            <label className="label">{t("ticketsetup.maxOpen")}</label>
            <input
              className="input"
              type="number"
              min={1}
              max={10}
              value={cfg.max_open}
              onChange={(e) =>
                setCfg({ ...cfg, max_open: Math.max(1, Math.min(10, Number(e.target.value))) })
              }
            />
          </div>
          <div>
            <label className="label">{t("ticketsetup.ticketNameFormat")}</label>
            <input
              className="input"
              value={cfg.ticket_name_format}
              onChange={(e) => setCfg({ ...cfg, ticket_name_format: e.target.value })}
            />
            <p className="mt-1 text-xs text-gray-500">{t("ticketsetup.ticketNameFormatHelp")}</p>
          </div>
        </div>

        <div>
          <label className="label">{t("ticketsetup.welcomeMessage")}</label>
          <textarea
            className="input resize-none"
            rows={3}
            placeholder={t("ticketsetup.welcomeMessagePlaceholder")}
            value={cfg.welcome_message}
            onChange={(e) => setCfg({ ...cfg, welcome_message: e.target.value })}
          />
        </div>

        <div>
          <label className="label">{t("ticketsetup.supportRoles")}</label>
          <p className="mb-2 text-xs text-gray-500">{t("ticketsetup.supportRolesDesc")}</p>
          {roles.length === 0 ? (
            <p className="text-sm text-gray-500">{t("ticketsetup.supportRolesEmpty")}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {roles.map((role) => {
                const active = cfg.support_role_ids.includes(role.id);
                return (
                  <button
                    key={role.id}
                    type="button"
                    onClick={() => toggleRole(role.id)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      active
                        ? "bg-wordlock-green/20 text-wordlock-green ring-1 ring-wordlock-green/40"
                        : "bg-white/10 text-gray-400 hover:bg-white/15"
                    }`}
                  >
                    {role.name}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {deployQueued && (
        <p className="text-sm text-wordlock-green">{t("ticketsetup.deployQueued")}</p>
      )}
      <p className="text-xs text-gray-500">{t("ticketsetup.deployHint")}</p>

      <div className="flex justify-end">
        <button onClick={save} className="btn-primary">
          <Save className="h-4 w-4" />
          {saved ? t("ticketsetup.saved") : t("ticketsetup.save")}
        </button>
      </div>
    </div>
  );
}
