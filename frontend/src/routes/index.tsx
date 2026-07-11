import { createFileRoute } from '@tanstack/react-router';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';
import { ArrowRight, Eye } from 'lucide-react';

export const Route = createFileRoute('/')({
  head: () => ({
    meta: [
      { title: 'BrandSightAI — AI brand monitoring' },
      { name: 'description', content: 'Track how your brand appears across the web with AI-powered monitoring.' },
      { property: 'og:title', content: 'BrandSightAI — AI brand monitoring' },
      { property: 'og:description', content: 'Track how your brand appears across the web with AI-powered monitoring.' },
      { property: 'og:url', content: '/' },
    ],
    links: [{ rel: 'canonical', href: '/' }],
  }),
  component: IndexPage,
});

function IndexPage() {
  const [value, setValue] = useState('');

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const v = value.trim();
    if (!v) {
      toast.error('Enter a brand or domain first');
      return;
    }
    toast.success(`Tracking ${v}`, {
      description: "We'll notify you when monitoring is ready.",
    });
    setValue('');
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-bs-bg text-bs-fg">
      {/* Ambient purple glows */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            'radial-gradient(60% 50% at 50% 20%, color-mix(in oklab, var(--bs-purple) 28%, transparent), transparent 70%), radial-gradient(45% 40% at 85% 90%, color-mix(in oklab, var(--bs-purple-deep) 35%, transparent), transparent 70%), radial-gradient(40% 35% at 10% 80%, color-mix(in oklab, var(--bs-purple) 18%, transparent), transparent 70%)',
        }}
      />
      {/* Subtle grain */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.06] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.6'/></svg>\")",
        }}
      />

      {/* Header */}
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-bs-purple to-bs-purple-deep shadow-[0_0_24px_-4px_var(--bs-purple)]">
            <Eye className="h-4 w-4 text-white" strokeWidth={2.5} />
          </div>
          <span className="font-display text-lg font-semibold tracking-tight">
            BrandSight<span className="text-bs-purple">AI</span>
          </span>
        </div>
      </header>

      {/* Hero */}
      <main className="mx-auto flex w-full max-w-3xl flex-col items-center px-6 pt-20 pb-24 text-center sm:pt-28">
        <span className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-bs-muted backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-bs-purple shadow-[0_0_8px_var(--bs-purple)]" />
          AI brand monitoring, in real time
        </span>

        <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl md:text-7xl">
          See how the internet
          <br />
          <span className="bg-gradient-to-r from-bs-purple via-fuchsia-400 to-bs-purple-deep bg-clip-text text-transparent">
            talks about your brand.
          </span>
        </h1>

        <p className="mt-6 max-w-xl text-base text-bs-muted sm:text-lg">
          Enter a brand or domain — BrandSightAI watches mentions, sentiment, and
          competitive moves so you don't have to.
        </p>

        <form onSubmit={onSubmit} className="mt-10 w-full max-w-xl">
          <div className="group relative flex items-center rounded-2xl border border-white/10 bg-white/[0.03] p-1.5 backdrop-blur transition-all focus-within:border-bs-purple/60 focus-within:shadow-[0_0_0_4px_color-mix(in_oklab,var(--bs-purple)_18%,transparent),0_0_40px_-8px_var(--bs-purple)] hover:border-white/20">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="Enter a brand or domain (e.g. Salesforce, HubSpot)"
              className="flex-1 bg-transparent px-4 py-3 text-base text-bs-fg placeholder:text-bs-muted/60 focus:outline-none"
              aria-label="Brand or domain to monitor"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-bs-purple to-bs-purple-deep px-5 py-3 text-sm font-medium text-white shadow-[0_8px_30px_-8px_var(--bs-purple)] transition-transform hover:-translate-y-px active:translate-y-0"
            >
              Track brand
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
          <p className="mt-3 text-xs text-bs-muted/70">
            Try: Salesforce · HubSpot · Notion · Linear
          </p>
        </form>
      </main>

      <footer className="mx-auto w-full max-w-6xl px-6 py-8 text-center text-xs text-bs-muted/60">
        © {new Date().getFullYear()} BrandSightAI. All rights reserved.
      </footer>
    </div>
  );
}
