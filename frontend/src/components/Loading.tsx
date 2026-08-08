/** Inline loader — uses span only so it is valid inside <p> and avoids hydration errors. */
export function Spinner({ label }: { label?: string }) {
  return (
    <span className="loading-inline" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label ? <span className="loading-label">{label}</span> : null}
    </span>
  );
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <div className="spinner spinner-lg" aria-hidden="true" />
      <p className="loading-label">{label}</p>
    </div>
  );
}

export function OpaqueScreenLoader({
  label,
  showSpinner = true,
}: {
  label?: string;
  showSpinner?: boolean;
}) {
  return (
    <div className="opaque-screen-loader" role="status" aria-live="polite" aria-busy="true">
      <div className="opaque-screen-loader-inner">
        {showSpinner ? <div className="spinner spinner-lg" aria-hidden="true" /> : null}
        {label ? <p className="loading-label">{label}</p> : null}
      </div>
    </div>
  );
}

export function StatsSkeleton({ count = 7 }: { count?: number }) {
  return (
    <div className="grid" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="card skeleton-card">
          <div className="skeleton skeleton-text-sm" />
          <div className="skeleton skeleton-value" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="table-wrap" aria-hidden="true">
      <table>
        <thead>
          <tr>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i}>
                <div className="skeleton skeleton-text-sm" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>
              {Array.from({ length: cols }).map((_, c) => (
                <td key={c}>
                  <div className="skeleton skeleton-text" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProfileSkeleton() {
  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }} aria-hidden="true">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="card skeleton-card">
          <div className="skeleton skeleton-text-sm" style={{ width: "40%" }} />
          <div className="skeleton skeleton-text" style={{ marginTop: "0.75rem" }} />
          <div className="skeleton skeleton-text" style={{ width: "80%", marginTop: "0.5rem" }} />
          <div className="skeleton skeleton-text" style={{ width: "60%", marginTop: "0.5rem" }} />
        </div>
      ))}
    </div>
  );
}
