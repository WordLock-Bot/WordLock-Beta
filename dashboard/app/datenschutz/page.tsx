import Link from "next/link";
import type { Metadata } from "next";
import { MaintenanceBanner } from "@/components/MaintenanceBanner";

export const metadata: Metadata = {
  title: "Privacy Policy — WordLock",
  description: "Privacy policy for WordLock.",
};

export default function DatenschutzPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/" className="text-sm text-blurple transition-colors hover:text-blurple/80">
        ← Back to home
      </Link>
      <h1 className="mt-6 text-3xl font-bold text-white">Privacy Policy</h1>
      <MaintenanceBanner />

      <section className="mt-8 space-y-8 text-sm leading-relaxed text-gray-300">
        <div className="card">
          <h2 className="text-lg font-semibold text-white">1. Responsible party</h2>
          <p className="mt-3">
            The party responsible for data processing within the meaning of the GDPR (General Data
            Protection Regulation) is the owner of WordLock. Contact details can be found in the{" "}
            <Link href="/impressum" className="text-blurple transition-colors hover:text-blurple/80">
              imprint
            </Link>
            .
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">2. Data collection on this website</h2>
          <p className="mt-3">
            This website is hosted by Vercel Inc., 340 S Lemon Ave #4133, Walnut, CA 91789, USA.
            When you visit this website, the hosting provider automatically collects technical data
            (e.g. IP address, time of access, browser type). This data is technically required to
            deliver the website. The legal basis is Art. 6 para. 1 lit. f GDPR.
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">3. Signing in via Discord (OAuth)</h2>
          <p className="mt-3">
            WordLock uses Discord&apos;s OAuth login for authentication. Discord provides your public
            user ID, username, and avatar. This data is used exclusively for authentication and for
            managing your servers in the dashboard. Discord data is only stored to the extent
            required for the dashboard to function.
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">4. Cookies</h2>
          <p className="mt-3">
            This website only uses technically necessary cookies or session data (authentication
            session) required to log into the dashboard. No third-party tracking or analytics
            cookies are used.
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">5. Your rights</h2>
          <p className="mt-3">
            You have the right to access, rectification, erasure, restriction of processing, data
            portability, and the right to object to processing (Art. 15–21 GDPR). You also have the
            right to lodge a complaint with a supervisory authority. Please send requests to the
            contact details listed in the imprint.
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">6. Server and message data</h2>
          <p className="mt-3">
            WordLock processes message content exclusively to perform moderation functions (e.g.
            automatic word filtering) on the Discord servers where the bot is enabled. The data
            stays in the server operator&apos;s own database and is never shared with third parties.
          </p>
        </div>
      </section>
    </main>
  );
}
