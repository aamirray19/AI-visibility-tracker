import { createFileRoute } from '@tanstack/react-router';
import { useCancelScan, useLaunch, useScan } from '@/hooks/api';
import { useStatusGuard } from '@/hooks/useStatusGuard';
import type { ScanStatus } from '@/lib/types';

export const Route = createFileRoute('/scans/$id/progress')({
  component: ProgressPage,
});

const IN_FLIGHT_STATUSES = new Set<ScanStatus>([
  'scope_pending',
  'queued',
  'generating_prompts',
  'executing',
  'evaluating',
  'aggregating',
]);
const isProgressStatus = (status: ScanStatus) => status === 'failed' || IN_FLIGHT_STATUSES.has(status);

const STAGE_LABELS: Record<string, string> = {
  enriching: 'Researching your company',
  generating_prompts: 'Writing test prompts',
  executing: 'Querying AI models',
  evaluating: 'Evaluating responses',
  aggregating: 'Crunching the numbers',
};

function ProgressPage() {
  const { id } = Route.useParams();
  const scan = useScan(id, {
    refetchInterval: (query) => (IN_FLIGHT_STATUSES.has(query.state.data?.status as ScanStatus) ? 2000 : false),
  });
  const launch = useLaunch(id);
  const cancel = useCancelScan(id);

  const status = scan.data?.status;

  // scope_pending is deliberately treated as "stay here, show Launch" --
  // PUT /scope (Phase 17) doesn't advance the status, so this page is the
  // one that owns the launch step for that status, diverging from
  // statusToPath's default (Scope page) which is only the cold-entry target.
  useStatusGuard(id, status, isProgressStatus);

  const progress = scan.data?.progress;
  const done = progress?.done ? Number(progress.done) : 0;
  const total = progress?.total ? Number(progress.total) : 0;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="flex min-h-screen items-center justify-center bg-bs-bg px-6 text-bs-fg">
      <div className="w-full max-w-md text-center">
        <h1 className="font-display text-3xl font-semibold">
          {scan.data?.company_name ? `Scanning ${scan.data.company_name}` : 'Scanning'}
        </h1>

        {status === 'scope_pending' && (
          <>
            <p className="mt-3 text-sm text-bs-muted">Ready to start monitoring.</p>
            <button
              type="button"
              onClick={() => launch.mutate()}
              disabled={launch.isPending}
              className="mt-8 rounded-xl bg-gradient-to-br from-bs-purple to-bs-purple-deep px-6 py-3 text-sm font-medium text-white disabled:opacity-60"
            >
              {launch.isPending ? 'Starting…' : 'Start scan'}
            </button>
          </>
        )}

        {status && status !== 'scope_pending' && status !== 'failed' && (
          <>
            <p className="mt-3 text-sm text-bs-muted">
              {STAGE_LABELS[progress?.stage ?? ''] ?? 'Working…'}
            </p>
            <div className="mt-6 h-2 w-full overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-bs-purple to-bs-purple-deep transition-all"
                style={{ width: `${total > 0 ? pct : 8}%` }}
              />
            </div>
            {total > 0 && (
              <p className="mt-2 text-xs text-bs-muted/70">
                {done} / {total}
              </p>
            )}
            <button
              type="button"
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className="mt-8 rounded-xl border border-white/10 px-5 py-2.5 text-sm text-bs-muted hover:border-white/30 disabled:opacity-60"
            >
              Cancel scan
            </button>
          </>
        )}

        {status === 'failed' && (
          <>
            <p className="mt-3 text-sm text-destructive">This scan failed to complete.</p>
            <a
              href="/"
              className="mt-8 inline-block rounded-xl border border-white/10 px-5 py-2.5 text-sm text-bs-fg hover:border-white/30"
            >
              Start a new scan
            </a>
          </>
        )}
      </div>
    </div>
  );
}
