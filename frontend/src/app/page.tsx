import React from "react";

export default function Home() {
  return (
    <main>
      <section className="shell" aria-labelledby="page-title">
        <div className="eyebrow">AI Visibility Tracker</div>
        <h1 id="page-title">Campaign analytics for brand visibility in AI answers</h1>
        <p>
          The baseline app shell is ready. Authentication, campaign creation, and dashboards are
          implemented in later phases.
        </p>
        <div className="status-row" aria-label="Phase 1 status">
          <div className="status-item">Next.js frontend</div>
          <div className="status-item">FastAPI backend</div>
          <div className="status-item">Local Postgres and Redis</div>
        </div>
      </section>
    </main>
  );
}
