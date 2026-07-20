import { createFileRoute } from '@tanstack/react-router';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { isTerminalStatus } from '@/lib/status';
import { useDashboard, useScan } from '@/hooks/api';
import { useStatusGuard } from '@/hooks/useStatusGuard';

export const Route = createFileRoute('/scans/$id/dashboard')({
  component: DashboardPage,
});

function DashboardPage() {
  const { id } = Route.useParams();
  const scan = useScan(id);
  const dashboard = useDashboard(id);

  useStatusGuard(id, scan.data?.status, isTerminalStatus);

  if (dashboard.isLoading || !dashboard.data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bs-bg text-bs-fg">
        <p className="text-bs-muted">Loading dashboard…</p>
      </div>
    );
  }

  const d = dashboard.data;
  const providers = d.by_provider.map((p) => p.provider);
  const targetEntry = d.leaderboard.find((e) => e.is_target);

  return (
    <div className="min-h-screen bg-bs-bg px-6 py-16 text-bs-fg">
      <div className="mx-auto max-w-5xl">
        <h1 className="font-display text-3xl font-semibold">
          {scan.data?.company_name ?? 'Dashboard'}
        </h1>

        {d.status === 'completed_with_gaps' && (
          <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-4 text-sm">
            <p className="font-medium text-amber-300">Partial results</p>
            <p className="mt-1 text-bs-muted">
              {d.status_detail ?? 'Some providers did not return complete results for this scan.'}
            </p>
          </div>
        )}
        <p className="mt-2 text-xs text-bs-muted/70">
          Based on {providers.length} provider{providers.length === 1 ? '' : 's'}: {providers.join(', ') || 'none'}
        </p>

        {/* Executive summary */}
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <SummaryTile label="AI Visibility" value={`${d.summary.ai_visibility}%`} />
          <SummaryTile label="Recommendation Rate" value={`${d.summary.recommendation_rate}%`} />
          <SummaryTile label="Share of Voice" value={`${d.summary.share_of_voice}%`} />
          <SummaryTile label="Net Sentiment" value={d.summary.net_sentiment.toFixed(2)} />
          <SummaryTile label="Responses Evaluated" value={`${d.summary.responses_evaluated} / ${d.summary.responses_total}`} />
          <SummaryTile
            label="Recommended (when mentioned)"
            value={`${d.summary.recommendation_rate_when_mentioned}%`}
          />
        </div>

        {/* Leaderboard / discovered competitors */}
        <Section title={d.brand_only ? 'Discovered competitors' : 'Competitor comparison'}>
          {d.brand_only ? (
            <ul className="divide-y divide-white/10">
              {d.discovered.map((c) => (
                <li key={c.name} className="flex items-center justify-between py-2 text-sm">
                  <span>{c.name}</span>
                  <span className="text-bs-muted">{c.mentions} mentions</span>
                </li>
              ))}
              {d.discovered.length === 0 && <p className="py-2 text-sm text-bs-muted">No other companies were mentioned.</p>}
            </ul>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-bs-muted">
                  <th className="pb-2 font-medium">Company</th>
                  <th className="pb-2 font-medium">Mentions</th>
                  <th className="pb-2 font-medium">Positive</th>
                  <th className="pb-2 font-medium">Negative</th>
                  <th className="pb-2 font-medium">Avg rank</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {d.leaderboard.map((entry) => (
                  <tr key={entry.entity_id} className={entry.is_target ? 'text-bs-purple' : undefined}>
                    <td className="py-2">{entry.name}{entry.is_target ? ' (you)' : ''}</td>
                    <td className="py-2">{entry.mentions}</td>
                    <td className="py-2">{entry.positive}</td>
                    <td className="py-2">{entry.negative}</td>
                    <td className="py-2">{entry.avg_rank ? entry.avg_rank.toFixed(1) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        {/* Sentiment breakdown */}
        {targetEntry && (
          <Section title="Sentiment breakdown">
            <div className="flex gap-6 text-sm">
              <SentimentStat label="Positive" count={targetEntry.positive} color="text-emerald-400" />
              <SentimentStat label="Neutral" count={targetEntry.neutral} color="text-bs-muted" />
              <SentimentStat label="Negative" count={targetEntry.negative} color="text-destructive" />
            </div>
          </Section>
        )}

        {/* Prompt category performance */}
        <Section title="Visibility by prompt category">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={d.by_category}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="category" tick={{ fill: 'var(--bs-muted)', fontSize: 12 }} />
              <YAxis tick={{ fill: 'var(--bs-muted)', fontSize: 12 }} unit="%" />
              <Tooltip contentStyle={{ background: 'var(--bs-bg)', border: '1px solid rgba(255,255,255,0.1)' }} />
              <Bar dataKey="visibility" fill="var(--bs-purple)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Section>

        {/* Provider comparison */}
        <Section title="Provider comparison">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.by_provider}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
              <XAxis dataKey="provider" tick={{ fill: 'var(--bs-muted)', fontSize: 12 }} />
              <YAxis tick={{ fill: 'var(--bs-muted)', fontSize: 12 }} unit="%" />
              <Tooltip contentStyle={{ background: 'var(--bs-bg)', border: '1px solid rgba(255,255,255,0.1)' }} />
              <Bar dataKey="visibility" fill="var(--bs-purple-deep)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <ul className="mt-2 flex gap-6 text-xs text-bs-muted">
            {d.by_provider.map((p) => (
              <li key={p.provider}>
                {p.provider}: {Math.round(p.success_rate * 100)}% success
              </li>
            ))}
          </ul>
        </Section>

        {/* Top sources */}
        <Section title="Where AI gets its information">
          <ul className="divide-y divide-white/10">
            {d.top_sources.map((s) => (
              <li key={s.domain} className="flex items-center justify-between py-2 text-sm">
                <span>{s.domain}</span>
                <span className="text-bs-muted">{s.responses} responses</span>
              </li>
            ))}
            {d.top_sources.length === 0 && <p className="py-2 text-sm text-bs-muted">No citations recorded.</p>}
          </ul>
        </Section>
      </div>
    </div>
  );
}

function SentimentStat({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div>
      <p className={`font-display text-xl font-semibold ${color}`}>{count}</p>
      <p className="text-xs text-bs-muted">{label}</p>
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <p className="text-xs text-bs-muted">{label}</p>
      <p className="mt-1 font-display text-2xl font-semibold">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="mb-3 text-sm font-semibold text-bs-muted">{title}</h2>
      <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">{children}</div>
    </section>
  );
}
