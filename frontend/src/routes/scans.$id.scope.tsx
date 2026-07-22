import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { MONITORING_CATEGORIES, type MonitoringCategory, type ScanStatus } from '@/lib/types';
import { useScan, useScope } from '@/hooks/api';
import { useStatusGuard } from '@/hooks/useStatusGuard';

export const Route = createFileRoute('/scans/$id/scope')({
  component: ScopePage,
});

const isScopeStatus = (status: ScanStatus) => status === 'scope_pending';

const CATEGORY_LABELS: Record<MonitoringCategory, string> = {
  brand_mentions: 'Brand mentions',
  product_recommendations: 'Product recommendations',
  competitor_comparisons: 'Competitor comparisons',
  purchase_intent: 'Purchase intent',
  feature_comparisons: 'Feature comparisons',
  alternatives: 'Alternatives',
  reviews: 'Reviews',
  pricing_discussions: 'Pricing discussions',
  technical_evaluations: 'Technical evaluations',
};

function ScopePage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const scan = useScan(id);
  const setScope = useScope(id);

  const [selected, setSelected] = useState<Set<MonitoringCategory>>(new Set(MONITORING_CATEGORIES));
  const [error, setError] = useState<string | null>(null);

  useStatusGuard(id, scan.data?.status, isScopeStatus);

  const toggle = (category: MonitoringCategory) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  const onSubmit = async () => {
    setError(null);
    try {
      await setScope.mutateAsync(Array.from(selected));
      navigate({ to: `/scans/${id}/progress` });
    } catch {
      setError('Could not save your monitoring scope. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-bs-bg px-6 py-16 text-bs-fg">
      <div className="mx-auto max-w-xl">
        <h1 className="font-display text-3xl font-semibold">What should we monitor?</h1>
        <p className="mt-2 text-sm text-bs-muted">
          Choose which kinds of questions to track. All 9 are selected by default.
        </p>

        <div className="mt-8 space-y-2">
          {MONITORING_CATEGORIES.map((category) => (
            <label
              key={category}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 text-sm hover:border-white/20"
            >
              <input
                type="checkbox"
                checked={selected.has(category)}
                onChange={() => toggle(category)}
                className="h-4 w-4 accent-bs-purple"
              />
              {CATEGORY_LABELS[category]}
            </label>
          ))}
        </div>

        {error && (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {error}
          </p>
        )}

        <button
          type="button"
          onClick={onSubmit}
          disabled={setScope.isPending}
          className="mt-8 rounded-xl bg-gradient-to-br from-bs-purple to-bs-purple-deep px-5 py-2.5 text-sm font-medium text-white disabled:opacity-60"
        >
          Start monitoring
        </button>
      </div>
    </div>
  );
}
