"use client";

import { useI18n } from "@/lib/i18n";

export function MaintenanceBanner() {
  const { t } = useI18n();
  return (
    <div className="mb-8 rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4 text-center">
      <p className="text-sm font-semibold text-yellow-400">
        {t("legal.maintenance.title")}
      </p>
      <p className="mt-1 text-sm text-yellow-200/80">
        {t("legal.maintenance.text")}
      </p>
    </div>
  );
}