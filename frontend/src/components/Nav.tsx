"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/applications", label: "Applications" },
  { href: "/inbox", label: "Inbox" },
  { href: "/logs", label: "Logs" },
  { href: "/profile", label: "Profile" },
];

export function Nav() {
  const path = usePathname();
  return (
    <aside className="sidebar">
      <div>
        <h1>Job OS</h1>
        <p className="tagline">Autonomous job pipeline</p>
        <nav>
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`nav-link ${path === l.href ? "active" : ""}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>

      <div style={{ marginTop: "auto", paddingTop: "2rem", opacity: 0.5, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <div style={{ fontSize: "0.6rem", fontFamily: "Cinzel, serif", letterSpacing: "0.15em", color: "var(--dew)", display: "flex", alignItems: "center" }}>
          <span className="status-dot ok" style={{ display: "inline-block", width: "6px", height: "6px", marginRight: "6px" }} />
          Colony Active
        </div>
        <svg viewBox="0 0 100 20" width="100%" height="20" fill="none">
          <path d="M 0 10 Q 25 15, 50 10 T 100 10" stroke="rgba(199, 242, 208, 0.25)" strokeWidth="0.8" />
        </svg>
      </div>
    </aside>
  );
}
