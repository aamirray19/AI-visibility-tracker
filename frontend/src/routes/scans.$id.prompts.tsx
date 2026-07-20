import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { isTerminalStatus } from '@/lib/status';
import { usePromptDetail, usePrompts, useScan, type PromptFilters } from '@/hooks/api';
import { useStatusGuard } from '@/hooks/useStatusGuard';

export const Route = createFileRoute('/scans/$id/prompts')({
  component: PromptsPage,
});

const PAGE_SIZE = 20;

function PromptsPage() {
  const { id } = Route.useParams();
  const scan = useScan(id);
  useStatusGuard(id, scan.data?.status, isTerminalStatus);

  const [filters, setFilters] = useState<PromptFilters>({ offset: 0, limit: PAGE_SIZE });
  const [expanded, setExpanded] = useState<string | null>(null);

  const prompts = usePrompts(id, filters);

  const setFilter = (key: keyof PromptFilters, value: string | boolean | undefined) => {
    setFilters((prev) => ({ ...prev, [key]: value, offset: 0 }));
    setExpanded(null);
  };

  const goToPage = (offset: number) => {
    setFilters((prev) => ({ ...prev, offset }));
    setExpanded(null);
  };

  const items = prompts.data?.items ?? [];
  const total = prompts.data?.total ?? 0;
  const offset = filters.offset ?? 0;

  return (
    <div className="min-h-screen bg-bs-bg px-6 py-16 text-bs-fg">
      <div className="mx-auto max-w-4xl">
        <h1 className="font-display text-3xl font-semibold">Prompt Explorer</h1>

        <div className="mt-6 flex flex-wrap gap-3">
          <FilterSelect
            label="Category"
            value={filters.category}
            options={['informational', 'commercial', 'competitor_discovery', 'product_specific']}
            onChange={(v) => setFilter('category', v)}
          />
          <FilterSelect
            label="Provider"
            value={filters.provider}
            options={['google_ai_studio', 'groq']}
            onChange={(v) => setFilter('provider', v)}
          />
          <FilterSelect
            label="Sentiment"
            value={filters.sentiment}
            options={['positive', 'neutral', 'negative']}
            onChange={(v) => setFilter('sentiment', v)}
          />
          <FilterSelect
            label="Mentioned"
            value={filters.mentioned === undefined ? undefined : String(filters.mentioned)}
            options={['true', 'false']}
            onChange={(v) => setFilter('mentioned', v === undefined ? undefined : v === 'true')}
          />
        </div>

        <div className="mt-6 divide-y divide-white/10 rounded-xl border border-white/10 bg-white/[0.03]">
          {items.map((item) => (
            <div key={item.id}>
              <button
                type="button"
                onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-white/[0.02]"
              >
                {expanded === item.id ? (
                  <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-bs-muted" />
                ) : (
                  <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-bs-muted" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{item.text}</p>
                  <div className="mt-1 flex flex-wrap gap-3 text-xs text-bs-muted">
                    <span>{item.category}</span>
                    {Object.entries(item.providers).map(([provider, summary]) => (
                      <span key={provider}>
                        {provider}: {summary.target_mentioned ? summary.sentiment ?? 'mentioned' : 'not mentioned'}
                      </span>
                    ))}
                  </div>
                </div>
              </button>
              {expanded === item.id && <PromptDetailPanel scanId={id} promptId={item.id} />}
            </div>
          ))}
          {items.length === 0 && !prompts.isLoading && (
            <p className="px-4 py-6 text-center text-sm text-bs-muted">No prompts match these filters.</p>
          )}
        </div>

        {total > PAGE_SIZE && (
          <div className="mt-4 flex items-center justify-between text-sm text-bs-muted">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => goToPage(Math.max(0, offset - PAGE_SIZE))}
              className="rounded-lg border border-white/10 px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => goToPage(offset + PAGE_SIZE)}
              className="rounded-lg border border-white/10 px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | undefined;
  options: string[];
  onChange: (value: string | undefined) => void;
}) {
  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || undefined)}
      className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-bs-fg focus:border-bs-purple/60 focus:outline-none"
      aria-label={label}
    >
      <option value="">{label}: any</option>
      {options.map((opt) => (
        <option key={opt} value={opt}>
          {opt}
        </option>
      ))}
    </select>
  );
}

function PromptDetailPanel({ scanId, promptId }: { scanId: string; promptId: string }) {
  const detail = usePromptDetail(scanId, promptId);

  if (detail.isLoading || !detail.data) {
    return <div className="px-4 pb-4 text-sm text-bs-muted">Loading…</div>;
  }

  return (
    <div className="space-y-4 border-t border-white/10 bg-white/[0.02] px-4 py-4">
      {detail.data.responses.map((response) => (
        <div key={response.provider} className="rounded-lg border border-white/10 p-3">
          <div className="flex items-center justify-between text-xs text-bs-muted">
            <span className="font-medium text-bs-fg">
              {response.provider} ({response.model})
            </span>
            <span>{response.status}</span>
          </div>
          {response.raw_response && (
            <p className="mt-2 whitespace-pre-wrap text-sm text-bs-fg/90">{response.raw_response}</p>
          )}
          {response.evaluation && (
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-bs-muted">
              <span>mentioned: {String(response.evaluation.target_mentioned)}</span>
              {response.evaluation.sentiment && <span>sentiment: {response.evaluation.sentiment}</span>}
              {response.evaluation.rank_position !== null && <span>rank: {response.evaluation.rank_position}</span>}
              <span>recommended: {String(response.evaluation.recommended)}</span>
              {response.evaluation.mentioned_companies.length > 0 && (
                <span>also mentioned: {response.evaluation.mentioned_companies.join(', ')}</span>
              )}
            </div>
          )}
          {response.citations.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-bs-muted">
              {response.citations.map((c, i) => (
                <span key={i} className="rounded-full border border-white/10 px-2 py-0.5">
                  {String(c.domain ?? c.url ?? 'source')}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
