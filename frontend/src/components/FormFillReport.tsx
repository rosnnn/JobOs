"use client";

export type FormAuditEntry = {
  page?: number;
  page_url?: string;
  question?: string;
  field_type?: string;
  required?: boolean;
  status?: string;
  filled?: string | null;
  notes?: string | null;
};

export type FormAudit = {
  ats?: string;
  total_fields_seen?: number;
  filled?: number;
  skipped?: number;
  captcha_detected?: boolean;
  captcha_type?: string | null;
  account_signup_required?: boolean;
  stopped_reason?: string | null;
  by_page?: Record<string, FormAuditEntry[]>;
  entries?: FormAuditEntry[];
};

function statusBadge(status?: string) {
  if (status === "filled") return "badge-approved";
  if (status === "captcha") return "badge-rejected";
  if (status === "skipped") return "badge-pending";
  return "badge-pending";
}

export function FormFillReport({ audit }: { audit: FormAudit }) {
  const entries = audit.entries ?? [];
  const byPage = audit.by_page ?? {};
  const pageKeys = Object.keys(byPage).sort((a, b) => Number(a) - Number(b));

  if (!entries.length && !pageKeys.length) {
    return (
      <p style={{ fontSize: "0.875rem", color: "var(--muted)" }}>
        No form fields captured yet. Run Dry-run apply on a Greenhouse/Lever/Workday link.
      </p>
    );
  }

  return (
    <div>
      <div className="actions" style={{ marginBottom: "0.75rem", flexWrap: "wrap" }}>
        {audit.ats && (
          <span className="badge badge-pending" style={{ textTransform: "uppercase" }}>
            {audit.ats}
          </span>
        )}
        <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
          {audit.filled ?? 0} filled · {audit.skipped ?? 0} skipped · {audit.total_fields_seen ?? entries.length}{" "}
          seen
        </span>
        {audit.captcha_detected && (
          <span className="badge badge-rejected">CAPTCHA: {audit.captcha_type || "detected"}</span>
        )}
        {audit.account_signup_required && (
          <span className="badge badge-pending">Account signup may be required</span>
        )}
      </div>

      {(pageKeys.length ? pageKeys : ["0"]).map((pageKey) => {
        const rows = byPage[pageKey] ?? entries.filter((e) => String(e.page ?? 0) === pageKey);
        if (!rows.length) return null;
        const pageUrl = rows[0]?.page_url;
        return (
          <div key={pageKey} style={{ marginBottom: "1.25rem" }}>
            <h4 style={{ fontSize: "0.9rem", marginBottom: "0.35rem" }}>
              Page {Number(pageKey) + 1}
              {pageUrl && (
                <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: "0.75rem", marginLeft: "0.5rem" }}>
                  ({(() => {
                    try {
                      return new URL(pageUrl).hostname;
                    } catch {
                      return pageUrl.slice(0, 40);
                    }
                  })()})
                </span>
              )}
            </h4>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table" style={{ fontSize: "0.8rem" }}>
                <thead>
                  <tr>
                    <th>Question / field</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>What we filled</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i}>
                      <td>
                        {row.question || "(unlabeled)"}
                        {row.required && (
                          <span style={{ color: "var(--warning)", marginLeft: "0.25rem" }}>*</span>
                        )}
                      </td>
                      <td>{row.field_type || "—"}</td>
                      <td>
                        <span className={`badge ${statusBadge(row.status)}`}>{row.status || "—"}</span>
                      </td>
                      <td style={{ maxWidth: "280px", wordBreak: "break-word" }}>
                        {row.status === "filled" ? row.filled || "—" : row.notes || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
