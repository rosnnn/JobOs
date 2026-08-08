import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import { ClientEffects } from "@/components/ClientEffects";
import { BootLoader } from "@/components/BootLoader";
import "./globals.css";

export const metadata: Metadata = {
  title: "Job OS Dashboard",
  description: "Autonomous job acquisition control panel",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <BootLoader />
        <ClientEffects />
        <div className="layout">
          <Nav />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

