import Link from "next/link";
import type { Metadata } from "next";
import { MaintenanceBanner } from "@/components/MaintenanceBanner";

export const metadata: Metadata = {
  title: "Imprint — WordLock",
  description: "Imprint for WordLock.",
};

export default function ImpressumPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/" className="text-sm text-blurple transition-colors hover:text-blurple/80">
        ← Back to home
      </Link>
      <h1 className="mt-6 text-3xl font-bold text-white">Imprint</h1>
      <MaintenanceBanner />

      <section className="mt-8 space-y-8 text-sm leading-relaxed text-gray-300">
        <div className="card">
          <h2 className="text-lg font-semibold text-white">Information in accordance with § 5 DDG</h2>
          <p className="mt-3">
            WordLock – Official moderation bot
            <br />
            Owner: DevCoder
            <br />
            Contact email: devcodermc@gmail.com
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">Contact</h2>
          <p className="mt-3">
            Email: devcodermc@gmail.com
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">Responsible for content</h2>
          <p className="mt-3">
            DevCoder
          </p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-white">Disclaimer</h2>
          <p className="mt-3">
            The content of this website has been created with the greatest care. However, no
            guarantee can be given for the accuracy, completeness, and up-to-dateness of the
            content. As a service provider, we are responsible for our own content on these pages
            in accordance with general law. We are not obligated to monitor transmitted or stored
            third-party information or to investigate circumstances that indicate illegal activity.
          </p>
        </div>
      </section>
    </main>
  );
}
