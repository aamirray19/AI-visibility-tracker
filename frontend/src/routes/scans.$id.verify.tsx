import { createFileRoute } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Plus, X } from 'lucide-react';
import type { Competitor, Product, ScanStatus } from '@/lib/types';
import { useConfirmProfile, usePatchProfile, useProfile, useScan } from '@/hooks/api';
import { useStatusGuard } from '@/hooks/useStatusGuard';

export const Route = createFileRoute('/scans/$id/verify')({
  component: VerifyPage,
});

interface Draft {
  industry: string;
  description: string;
  aliases: string[];
  products: Product[];
  competitors: Competitor[];
}

function draftFromProfile(profile: { industry: string | null; description: string | null; aliases: string[]; products: Product[]; competitors: Competitor[] }): Draft {
  return {
    industry: profile.industry ?? '',
    description: profile.description ?? '',
    aliases: [...profile.aliases],
    products: profile.products.map((p) => ({ ...p })),
    competitors: profile.competitors.map((c) => ({ ...c, aliases: [...c.aliases] })),
  };
}

const VERIFY_STATUSES: ScanStatus[] = ['awaiting_verification', 'verifying'];
const isVerifyStatus = (status: ScanStatus) => VERIFY_STATUSES.includes(status);

function VerifyPage() {
  const { id } = Route.useParams();
  const queryClient = useQueryClient();

  const scan = useScan(id, {
    refetchInterval: (query) => (query.state.data?.status === 'verifying' ? 1500 : false),
  });
  const profile = useProfile(id);
  const patchProfile = usePatchProfile(id);
  const confirmProfile = useConfirmProfile(id);

  const [draft, setDraft] = useState<Draft | null>(null);
  const syncedVersion = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Redirect away once the scan has moved past verification (also covers a
  // reload mid-flow: GET /scans/{id} is the source of truth for where to land).
  useStatusGuard(id, scan.data?.status, isVerifyStatus);

  // Re-fetch the profile once verify_profile's async critique job settles
  // (verifying -> awaiting_verification with issues attached to this row).
  useEffect(() => {
    if (scan.data?.status === 'awaiting_verification') {
      queryClient.invalidateQueries({ queryKey: ['profile', id] });
    }
  }, [scan.data?.status, id, queryClient]);

  // Reset the editable draft whenever a new profile version arrives --
  // never while the user is mid-edit on the version they're already looking at.
  useEffect(() => {
    if (profile.data && profile.data.version !== syncedVersion.current) {
      setDraft(draftFromProfile(profile.data));
      syncedVersion.current = profile.data.version;
    }
  }, [profile.data]);

  if (!draft || !profile.data) {
    return <PageShell companyName={scan.data?.company_name}>Loading profile…</PageShell>;
  }

  const verifying = scan.data?.status === 'verifying';
  const issues = profile.data.issues;

  const onSave = async () => {
    setError(null);
    try {
      await patchProfile.mutateAsync({
        industry: draft.industry,
        description: draft.description,
        aliases: draft.aliases,
        products: draft.products,
        competitors: draft.competitors,
      });
    } catch {
      setError('Could not save your changes. Please try again.');
    }
  };

  const onConfirm = async () => {
    setError(null);
    try {
      await onSave();
      await confirmProfile.mutateAsync();
      await scan.refetch();
    } catch {
      setError('Could not confirm the profile. Please try again.');
    }
  };

  const removeIssueField = (issue: (typeof issues)[number]) => {
    if (issue.field === 'aliases') {
      setDraft({ ...draft, aliases: draft.aliases.filter((a) => a !== issue.value) });
    } else if (issue.field === 'competitors') {
      setDraft({ ...draft, competitors: draft.competitors.filter((c) => c.name !== issue.value) });
    } else if (issue.field === 'products') {
      setDraft({ ...draft, products: draft.products.filter((p) => p.name !== issue.value) });
    }
  };

  return (
    <PageShell companyName={scan.data?.company_name} website={scan.data?.company_domain}>
      {verifying ? (
        <p className="text-bs-muted">Running the accuracy check…</p>
      ) : (
        <>
          {issues.length > 0 && (
            <section className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/[0.06] p-4">
              <h2 className="mb-2 text-sm font-semibold text-amber-300">Flagged by the accuracy check</h2>
              <ul className="space-y-2">
                {issues.map((issue, i) => (
                  <li key={i} className="flex items-start justify-between gap-3 text-sm">
                    <span>
                      <span className="font-medium">{issue.field}</span> — {issue.value}: {issue.reason}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeIssueField(issue)}
                      className="shrink-0 rounded-md border border-white/10 px-2 py-1 text-xs text-bs-muted hover:border-white/30"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-bs-muted">
                Remove anything wrong above, or confirm again to accept the profile as-is.
              </p>
            </section>
          )}

          <TextField label="Industry" value={draft.industry} onChange={(v) => setDraft({ ...draft, industry: v })} />
          <TextArea
            label="Description"
            value={draft.description}
            onChange={(v) => setDraft({ ...draft, description: v })}
          />

          <StringListField
            label="Aliases"
            items={draft.aliases}
            onChange={(aliases) => setDraft({ ...draft, aliases })}
          />

          <ProductsField products={draft.products} onChange={(products) => setDraft({ ...draft, products })} />

          <CompetitorsField
            competitors={draft.competitors}
            onChange={(competitors) => setDraft({ ...draft, competitors })}
          />

          {error && (
            <p role="alert" className="mt-4 text-sm text-destructive">
              {error}
            </p>
          )}

          <div className="mt-8 flex gap-3">
            <button
              type="button"
              onClick={onSave}
              disabled={patchProfile.isPending}
              className="rounded-xl border border-white/10 px-5 py-2.5 text-sm font-medium text-bs-fg hover:border-white/30 disabled:opacity-60"
            >
              Save
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={patchProfile.isPending || confirmProfile.isPending}
              className="rounded-xl bg-gradient-to-br from-bs-purple to-bs-purple-deep px-5 py-2.5 text-sm font-medium text-white disabled:opacity-60"
            >
              {issues.length > 0 ? 'Confirm as-is' : 'Confirm'}
            </button>
          </div>
        </>
      )}
    </PageShell>
  );
}

function PageShell({
  children,
  companyName,
  website,
}: {
  children: React.ReactNode;
  companyName?: string | null;
  website?: string | null;
}) {
  return (
    <div className="min-h-screen bg-bs-bg px-6 py-16 text-bs-fg">
      <div className="mx-auto max-w-2xl">
        <h1 className="font-display text-3xl font-semibold">Verify your company profile</h1>
        {companyName && (
          <p className="mt-2 text-sm text-bs-muted">
            {companyName}
            {website ? ` · ${website}` : ''} <span className="text-bs-muted/60">(locked)</span>
          </p>
        )}
        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="mb-6 block">
      <span className="mb-1.5 block text-sm font-medium text-bs-muted">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-bs-fg focus:border-bs-purple/60 focus:outline-none"
      />
    </label>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="mb-6 block">
      <span className="mb-1.5 block text-sm font-medium text-bs-muted">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-bs-fg focus:border-bs-purple/60 focus:outline-none"
      />
    </label>
  );
}

function StringListField({
  label,
  items,
  onChange,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
}) {
  const [draftValue, setDraftValue] = useState('');
  return (
    <div className="mb-6">
      <span className="mb-1.5 block text-sm font-medium text-bs-muted">{label}</span>
      <div className="mb-2 flex flex-wrap gap-2">
        {items.map((item, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs"
          >
            {item}
            <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label={`Remove ${item}`}>
              <X className="h-3 w-3 text-bs-muted hover:text-bs-fg" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={draftValue}
          onChange={(e) => setDraftValue(e.target.value)}
          placeholder={`Add ${label.toLowerCase()}`}
          className="flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm text-bs-fg focus:border-bs-purple/60 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => {
            if (draftValue.trim()) {
              onChange([...items, draftValue.trim()]);
              setDraftValue('');
            }
          }}
          className="rounded-lg border border-white/10 p-1.5 hover:border-white/30"
          aria-label={`Add ${label.toLowerCase()}`}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function ProductsField({
  products,
  onChange,
}: {
  products: Product[];
  onChange: (products: Product[]) => void;
}) {
  return (
    <div className="mb-6">
      <span className="mb-1.5 block text-sm font-medium text-bs-muted">Products</span>
      <div className="space-y-2">
        {products.map((product, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="text"
              value={product.name}
              onChange={(e) => onChange(products.map((p, j) => (j === i ? { ...p, name: e.target.value } : p)))}
              placeholder="Product name"
              className="flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm focus:border-bs-purple/60 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => onChange(products.filter((_, j) => j !== i))}
              aria-label={`Remove ${product.name}`}
              className="rounded-lg border border-white/10 p-1.5 hover:border-white/30"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => onChange([...products, { name: '', description: null }])}
        className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:border-white/30"
      >
        <Plus className="h-3.5 w-3.5" /> Add product
      </button>
    </div>
  );
}

function CompetitorsField({
  competitors,
  onChange,
}: {
  competitors: Competitor[];
  onChange: (competitors: Competitor[]) => void;
}) {
  return (
    <div className="mb-6">
      <span className="mb-1.5 block text-sm font-medium text-bs-muted">Competitors</span>
      <div className="space-y-2">
        {competitors.map((competitor, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="text"
              value={competitor.name}
              onChange={(e) =>
                onChange(competitors.map((c, j) => (j === i ? { ...c, name: e.target.value } : c)))
              }
              placeholder="Competitor name"
              className="flex-1 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm focus:border-bs-purple/60 focus:outline-none"
            />
            <input
              type="text"
              value={competitor.domain ?? ''}
              onChange={(e) =>
                onChange(competitors.map((c, j) => (j === i ? { ...c, domain: e.target.value } : c)))
              }
              placeholder="Domain (optional)"
              className="w-40 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm focus:border-bs-purple/60 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => onChange(competitors.filter((_, j) => j !== i))}
              aria-label={`Remove ${competitor.name}`}
              className="rounded-lg border border-white/10 p-1.5 hover:border-white/30"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => onChange([...competitors, { name: '', domain: null, aliases: [] }])}
        className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:border-white/30"
      >
        <Plus className="h-3.5 w-3.5" /> Add competitor
      </button>
    </div>
  );
}
