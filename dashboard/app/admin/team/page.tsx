"use client";

import { useEffect, useState } from "react";
import { Plus, Save, Trash2, Users } from "lucide-react";
import { api } from "@/lib/api";
import type { TeamMember } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const EMPTY = {
  name: "",
  role: "",
  parent_id: null as number | null,
  sort_order: 0,
  discord_id: null as number | null,
  panel_access: false,
};

export default function AdminTeam() {
  const { t } = useI18n();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = () => api<TeamMember[]>("/api/admin/team").then(setMembers);

  useEffect(() => {
    reload().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (!form.name.trim()) return;
    setBusy(true);
    try {
      await api(editing ? `/api/admin/team/${editing}` : "/api/admin/team", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(form),
      });
      setForm(EMPTY);
      setEditing(null);
      setMsg(t("adTeam.saved"));
      await reload();
    } catch (e) {
      setErr((e as Error).message || t("webticket.errorGeneric"));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (m: TeamMember) => {
    setEditing(m.id);
    setForm({
      name: m.name,
      role: m.role,
      parent_id: m.parent_id,
      sort_order: m.sort_order,
      discord_id: m.discord_id,
      panel_access: m.panel_access,
    });
  };

  const toggleAccess = async (m: TeamMember) => {
    const next = !m.panel_access;
    try {
      await api(`/api/admin/team/${m.id}`, {
        method: "PUT",
        body: JSON.stringify({ panel_access: next }),
      });
      await reload();
    } catch {
      /* keep current state on failure */
    }
  };

  const remove = async (m: TeamMember) => {
    if (!window.confirm(t("adTeam.deleteConfirm", { name: m.name }))) return;
    await api(`/api/admin/team/${m.id}`, { method: "DELETE" });
    await reload();
  };

  const cancel = () => {
    setEditing(null);
    setForm(EMPTY);
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("adTeam.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("adTeam.subtitle")}</p>
      </header>

      {msg && <div className="rounded-lg bg-wordlock-green/10 px-4 py-3 text-sm text-wordlock-green">{msg}</div>}

      <form onSubmit={submit} className="card space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="label">{t("adTeam.name")}</label>
            <input
              className="input w-56"
              value={form.name}
              placeholder={t("adTeam.namePlaceholder")}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="label">{t("adTeam.role")}</label>
            <input
              className="input w-64"
              value={form.role}
              placeholder={t("adTeam.rolePlaceholder")}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            />
          </div>
          <div>
            <label className="label">{t("adTeam.parent")}</label>
            <select
              className="input w-48"
              value={form.parent_id ?? ""}
              onChange={(e) =>
                setForm({ ...form, parent_id: e.target.value ? Number(e.target.value) : null })
              }
            >
              <option value="">{t("adTeam.noParent")}</option>
              {members
                .filter((m) => m.id !== editing)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label className="label">{t("adTeam.sortOrder")}</label>
            <input
              type="number"
              className="input w-24"
              value={form.sort_order}
              onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })}
            />
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="label">{t("adTeam.discordId")}</label>
            <input
              className="input w-56"
              inputMode="numeric"
              value={form.discord_id ?? ""}
              placeholder={t("adTeam.discordIdPlaceholder")}
              onChange={(e) =>
                setForm({
                  ...form,
                  discord_id: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
            <p className="mt-1 text-xs text-gray-500">{t("adTeam.discordIdDesc")}</p>
          </div>
          <label className="flex cursor-pointer items-center gap-2 pb-1">
            <input
              type="checkbox"
              checked={form.panel_access}
              onChange={(e) => setForm({ ...form, panel_access: e.target.checked })}
              className="h-4 w-4 accent-blurple"
            />
            <span className="text-sm font-medium text-gray-200">{t("adTeam.panelAccess")}</span>
          </label>
          <p className="pb-1 text-xs text-gray-500">{t("adTeam.panelAccessDesc")}</p>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary">
              {editing ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {editing ? t("common.save") : t("common.add")}
            </button>
            {editing && (
              <button type="button" onClick={cancel} className="btn-secondary">
                {t("common.cancel")}
              </button>
            )}
          </div>
        </div>
      </form>

      {err && (
        <div className="rounded-lg bg-wordlock-red/10 px-4 py-3 text-sm text-wordlock-red">
          {err}
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-gray-400">
              <th className="pb-2">{t("adTeam.thName")}</th>
              <th className="pb-2">{t("adTeam.thRole")}</th>
              <th className="pb-2">{t("adTeam.thParent")}</th>
              <th className="pb-2">{t("adTeam.thOrder")}</th>
              <th className="pb-2">{t("adTeam.thAccess")}</th>
              <th className="pb-2 text-right">{t("adTeam.thActions")}</th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id} className="border-b border-white/5 last:border-0">
                <td className="py-3">
                  <div className="flex items-center gap-2 font-medium text-white">
                    <Users className="h-4 w-4 text-blurple" /> {m.name}
                  </div>
                </td>
                <td className="py-3 text-gray-300">{m.role}</td>
                <td className="py-3 text-gray-400">
                  {members.find((p) => p.id === m.parent_id)?.name ?? "—"}
                </td>
                <td className="py-3 font-mono text-xs text-gray-400">{m.sort_order}</td>
                <td className="py-3">
                  <button
                    onClick={() => toggleAccess(m)}
                    title={m.discord_id ? t("adTeam.panelAccessDesc") : t("adTeam.discordIdDesc")}
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium transition ${
                      m.panel_access
                        ? "bg-wordlock-green/15 text-wordlock-green hover:bg-wordlock-green/25"
                        : "bg-white/10 text-gray-400 hover:bg-white/15"
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${m.panel_access ? "bg-wordlock-green" : "bg-gray-500"}`} />
                    {m.panel_access ? t("common.yes") : t("common.no")}
                  </button>
                </td>
                <td className="py-3">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => startEdit(m)} className="btn-secondary px-2 py-1 text-xs">
                      {t("common.edit")}
                    </button>
                    <button onClick={() => remove(m)} className="btn-danger px-2 py-1 text-xs">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {members.length === 0 && (
              <tr>
                <td colSpan={6} className="py-10 text-center text-gray-500">
                  {t("adTeam.empty")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
