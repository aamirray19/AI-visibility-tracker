"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle, Clock, Activity, Zap, Filter, ArrowLeft, X, Bot } from "lucide-react";
import { clsx } from "clsx";
import { motion, AnimatePresence } from "framer-motion";
import MetricsGrid from "@/components/dashboard/MetricsGrid";
import CompetitorLeaderboard from "@/components/dashboard/CompetitorLeaderboard";
import TopCitedPages from "@/components/dashboard/TopCitedPages";
import ModelComparisonPanel from "@/components/dashboard/ModelComparisonPanel";

// ─── Types ─────────────────────────────────────────────────────────────────

interface PromptResult {
    id: number;
    text: string;
    intent: string;
    status: string;
    rank: number | null;
    sentiment: number | null;
    response_text: string | null;
    platform: string;
}

interface AdvancedMetrics {
    ai_visibility: number;
    citation_share: number;
    share_of_voice: number;
    average_rank: number;
    average_sentiment: number;
    total_mentions: number;
    total_citations: number;
}

interface ModelMetrics {
    platform: string;
    ai_visibility: number;
    average_rank: number;
    average_sentiment: number;
    total_mentions: number;
    total_results: number;
}

interface CompetitorStats {
    name: string;
    mention_count: number;
    ai_visibility: number;
    average_rank: number;
    average_sentiment: number;
}

interface CitedPage {
    url: string;
    domain: string;
    mention_count: number;
    is_target_brand: boolean;
}

interface PaginationMeta {
    page: number;
    page_size: number;
    total_results: number;
    total_pages: number;
}

interface CampaignDashboard {
    id: number;
    brand: string;
    total_prompts: number;
    processed_count: number;
    is_complete: boolean;
    metrics: AdvancedMetrics;
    per_model_metrics: ModelMetrics[];
    competitors: CompetitorStats[];
    top_cited_pages: CitedPage[];
    mentioned_prompts: PromptResult[];
    results: PromptResult[];
    pagination: PaginationMeta;
}

// ─── Platform badge colours ──────────────────────────────────────────────────

const PLATFORM_STYLES: Record<string, string> = {
    gpt: "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400",
    gemma: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400",
};

// ─── Response Modal ──────────────────────────────────────────────────────────

function ResponseModal({ text, platform, onClose }: { text: string; platform: string; onClose: () => void }) {
    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
            onClick={onClose}
        >
            <motion.div
                initial={{ scale: 0.92, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.92, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[82vh] flex flex-col border border-slate-200 dark:border-slate-700"
            >
                <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                    <div>
                        <h3 className="font-bold text-lg text-slate-900 dark:text-slate-50">AI Response</h3>
                        <span className={clsx("text-xs font-bold uppercase px-2 py-0.5 rounded-full", PLATFORM_STYLES[platform] ?? "bg-slate-100 text-slate-600")}>
                            {platform}
                        </span>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                        aria-label="Close"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <div className="px-6 py-5 overflow-y-auto whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300 font-mono bg-slate-50 dark:bg-slate-950 leading-relaxed rounded-b-2xl">
                    {text}
                </div>
            </motion.div>
        </div>
    );
}

// ─── Progress Section ────────────────────────────────────────────────────────

function ProgressSection({ processed, total }: { processed: number; total: number }) {
    const pct = total > 0 ? (processed / total) * 100 : 0;
    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white dark:bg-slate-900 rounded-2xl p-5 shadow-sm border border-slate-200 dark:border-slate-800"
        >
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                    <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-2 rounded-lg">
                        <Activity className="w-4 h-4 text-white" />
                    </div>
                    <div>
                        <h3 className="font-bold text-slate-900 dark:text-slate-50">Processing Progress</h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                            {processed} of {total} prompts analyzed
                        </p>
                    </div>
                </div>
                <div className="text-2xl font-black bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                    {pct.toFixed(1)}%
                </div>
            </div>

            <div className="relative h-3 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.5, ease: "easeOut" }}
                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 rounded-full"
                />
                <motion.div
                    animate={{ x: ["-100%", "400%"] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                    className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                />
            </div>

            <div className="mt-2.5 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                <Zap className="w-3.5 h-3.5 text-yellow-500 animate-pulse" />
                Processing in real-time — page auto-refreshes
            </div>
        </motion.div>
    );
}

// ─── Results Table ────────────────────────────────────────────────────────────

function ResultsTable({
    results,
    brand,
    onViewResponse,
    showOnlyMentions,
    onToggleFilter,
    mentionCount,
}: {
    results: PromptResult[];
    brand: string;
    onViewResponse: (text: string, platform: string) => void;
    showOnlyMentions: boolean;
    onToggleFilter: () => void;
    mentionCount: number;
}) {
    return (
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
            {/* Table Header */}
            <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
                <div>
                    <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">
                        {showOnlyMentions ? "Brand Mentions" : "All Results"}
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                        {showOnlyMentions
                            ? `${mentionCount} prompts where ${brand} was mentioned`
                            : "Full breakdown of every query across both models"}
                    </p>
                </div>
                <button
                    onClick={onToggleFilter}
                    className={clsx(
                        "flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all flex-shrink-0",
                        showOnlyMentions
                            ? "bg-indigo-600 text-white shadow"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                    )}
                >
                    <Filter className="w-4 h-4" />
                    {showOnlyMentions ? "Show All" : "Mentions Only"}
                </button>
            </div>

            {results.length === 0 ? (
                <div className="py-16 text-center text-slate-400 dark:text-slate-500">
                    <Bot className="w-10 h-10 mx-auto mb-3 opacity-40" />
                    <p className="font-medium">No results yet — processing is underway</p>
                    <p className="text-sm mt-1">Results will appear here as each prompt is analyzed</p>
                </div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-400 text-xs uppercase tracking-wider">
                            <tr>
                                <th className="px-5 py-3.5 font-semibold">Prompt</th>
                                <th className="px-5 py-3.5 font-semibold">Intent</th>
                                <th className="px-5 py-3.5 font-semibold">Status</th>
                                <th className="px-5 py-3.5 font-semibold">Rank</th>
                                <th className="px-5 py-3.5 font-semibold">Sentiment</th>
                                <th className="px-5 py-3.5 font-semibold">Model</th>
                                <th className="px-5 py-3.5 font-semibold text-right">Response</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                            {results.map((result) => (
                                <tr
                                    key={result.id}
                                    className="hover:bg-slate-50/60 dark:hover:bg-slate-800/30 transition-colors"
                                >
                                    <td className="px-5 py-3.5 text-slate-800 dark:text-slate-200 font-medium max-w-xs truncate text-sm">
                                        {result.text}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <span
                                            className={clsx(
                                                "px-2 py-0.5 rounded-full text-xs font-semibold",
                                                result.intent === "commercial"
                                                    ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                                                    : "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400"
                                            )}
                                        >
                                            {result.intent}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {result.status === "COMPLETED" ? (
                                            <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
                                                <CheckCircle className="w-3.5 h-3.5" />
                                                Done
                                            </div>
                                        ) : (
                                            <div className="flex items-center gap-1.5 text-amber-500 text-xs font-semibold">
                                                <Clock className="w-3.5 h-3.5 animate-pulse" />
                                                Pending
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {result.rank ? (
                                            <span className="font-bold text-slate-800 dark:text-slate-200">
                                                #{result.rank}
                                            </span>
                                        ) : (
                                            <span className="text-slate-300 dark:text-slate-600">—</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {result.sentiment !== null ? (
                                            <div className="flex items-center gap-2">
                                                <div className="w-16 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                                    <div
                                                        className={clsx(
                                                            "h-full rounded-full",
                                                            result.sentiment > 0.6
                                                                ? "bg-emerald-500"
                                                                : result.sentiment < 0.4
                                                                    ? "bg-red-500"
                                                                    : "bg-amber-400"
                                                        )}
                                                        style={{ width: `${result.sentiment * 100}%` }}
                                                    />
                                                </div>
                                                <span className="text-xs text-slate-500 dark:text-slate-400">
                                                    {(result.sentiment * 100).toFixed(0)}%
                                                </span>
                                            </div>
                                        ) : (
                                            <span className="text-slate-300 dark:text-slate-600">—</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5">
                                        {result.platform ? (
                                            <span className={clsx("text-xs font-bold uppercase px-2 py-0.5 rounded-full", PLATFORM_STYLES[result.platform] ?? "bg-slate-100 dark:bg-slate-800 text-slate-500")}>
                                                {result.platform}
                                            </span>
                                        ) : (
                                            <span className="text-slate-300 dark:text-slate-600">—</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3.5 text-right">
                                        {result.response_text ? (
                                            <button
                                                onClick={() => onViewResponse(result.response_text!, result.platform)}
                                                className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-semibold text-xs border border-indigo-200 dark:border-indigo-800 px-2.5 py-1 rounded-lg hover:bg-indigo-50 dark:hover:bg-indigo-950/40 transition-colors"
                                            >
                                                View
                                            </button>
                                        ) : (
                                            <span className="text-slate-300 dark:text-slate-700 text-sm">···</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function CampaignDashboardPage() {
    const params = useParams();
    const router = useRouter();
    const [data, setData] = useState<CampaignDashboard | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedResponse, setSelectedResponse] = useState<{ text: string; platform: string } | null>(null);
    const [showOnlyMentions, setShowOnlyMentions] = useState(false);
    const [recentActivity, setRecentActivity] = useState<PromptResult[]>([]);

    // Use a ref to track previous results without adding `data` to dep array
    const prevResultsRef = useRef<PromptResult[]>([]);

    const fetchData = useCallback(async () => {
        try {
            const res = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/campaigns/${params.id}`
            );
            if (!res.ok) return;
            const json: CampaignDashboard = await res.json();

            // Track newly completed items for live activity feed
            const newCompleted = json.results.filter(
                (r) =>
                    r.status === "COMPLETED" &&
                    !prevResultsRef.current.find((old) => old.id === r.id && old.status === "COMPLETED")
            );
            if (newCompleted.length > 0) {
                setRecentActivity((prev) => [...newCompleted.slice(0, 3), ...prev].slice(0, 5));
            }
            prevResultsRef.current = json.results;

            setData(json);
        } catch (err) {
            console.error("Failed to fetch dashboard", err);
        } finally {
            setLoading(false);
        }
    }, [params.id]);

    useEffect(() => {
        fetchData();
        // H2 fix: stop polling when campaign is complete — no need to keep hitting the API
        if (data?.is_complete) return;
        const interval = setInterval(fetchData, 3000);
        return () => clearInterval(interval);
    }, [fetchData, data?.is_complete]);

    // ── Loading state ──────────────────────────────────────────────────────────
    if (loading && !data) {
        return (
            <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
                <div className="text-center space-y-4">
                    <div className="w-14 h-14 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
                    <p className="text-slate-500 dark:text-slate-400 font-medium">Loading campaign…</p>
                </div>
            </div>
        );
    }

    if (!data) {
        return (
            <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
                <div className="text-center space-y-3">
                    <p className="text-lg font-semibold text-red-500">Campaign not found</p>
                    <button
                        onClick={() => router.push("/")}
                        className="text-indigo-600 dark:text-indigo-400 text-sm underline"
                    >
                        ← Back to home
                    </button>
                </div>
            </div>
        );
    }

    // Use the authoritative is_complete flag from the backend
    const isComplete = data.is_complete;
    const displayResults = showOnlyMentions ? data.mentioned_prompts : data.results;

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/20 to-purple-50/10 dark:from-slate-950 dark:via-indigo-950/10 dark:to-purple-950/10 p-5 md:p-8">
            <div className="max-w-7xl mx-auto space-y-5">

                {/* ── Top Nav ─────────────────────────────────────────────────────── */}
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <button
                            onClick={() => router.push("/")}
                            className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors font-medium mb-2"
                        >
                            <ArrowLeft className="w-4 h-4" />
                            New Campaign
                        </button>
                        <h1 className="text-4xl md:text-5xl font-black bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 bg-clip-text text-transparent leading-tight">
                            {data.brand}
                        </h1>
                        <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">Campaign Analytics Dashboard</p>
                    </div>

                    {isComplete && (
                        <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            className="flex items-center gap-2 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 px-4 py-2 rounded-full font-bold text-sm border border-emerald-200 dark:border-emerald-800 flex-shrink-0"
                        >
                            <CheckCircle className="w-4 h-4" />
                            Complete
                        </motion.div>
                    )}
                </div>

                {/* ── Progress (while running) ─────────────────────────────────────── */}
                {!isComplete && (
                    <ProgressSection processed={data.processed_count} total={data.total_prompts} />
                )}

                {/* ── Metrics ─────────────────────────────────────────────────────── */}
                <MetricsGrid metrics={data.metrics} />

                {/* ── Model Comparison ─────────────────────────────────────────────── */}
                {data.per_model_metrics && data.per_model_metrics.length > 0 && (
                    <ModelComparisonPanel perModelMetrics={data.per_model_metrics} />
                )}

                {/* ── Competitor Leaderboard ───────────────────────────────────────── */}
                {data.competitors.length > 0 && (
                    <CompetitorLeaderboard competitors={data.competitors} targetBrand={data.brand} />
                )}

                {/* ── Top Cited Pages ──────────────────────────────────────────────── */}
                {data.top_cited_pages.length > 0 && (
                    <TopCitedPages pages={data.top_cited_pages} />
                )}

                {/* ── Live Activity Feed ───────────────────────────────────────────── */}
                <AnimatePresence>
                    {recentActivity.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -16 }}
                            className="bg-white dark:bg-slate-900 rounded-2xl p-5 shadow-sm border border-slate-200 dark:border-slate-800"
                        >
                            <h3 className="font-bold text-slate-900 dark:text-slate-50 mb-3 flex items-center gap-2 text-base">
                                <Zap className="w-4 h-4 text-yellow-500" />
                                Live Activity
                            </h3>
                            <div className="space-y-2">
                                <AnimatePresence>
                                    {recentActivity.map((item) => (
                                        <motion.div
                                            key={item.id}
                                            initial={{ opacity: 0, x: -16 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: 16 }}
                                            className="flex items-start gap-2.5 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-100 dark:border-slate-700/50"
                                        >
                                            <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
                                                    {item.text}
                                                </p>
                                                <div className="flex items-center gap-2.5 mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                                    <span>Rank: {item.rank ? `#${item.rank}` : "—"}</span>
                                                    {item.sentiment !== null && (
                                                        <span>· Sentiment: {(item.sentiment * 100).toFixed(0)}%</span>
                                                    )}
                                                    {item.platform && (
                                                        <span className={clsx("font-bold uppercase px-1.5 py-0.5 rounded-full text-xs", PLATFORM_STYLES[item.platform] ?? "bg-slate-100 text-slate-500")}>
                                                            {item.platform}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* ── Results Table ────────────────────────────────────────────────── */}
                <ResultsTable
                    results={displayResults}
                    brand={data.brand}
                    onViewResponse={(text, platform) => setSelectedResponse({ text, platform })}
                    showOnlyMentions={showOnlyMentions}
                    onToggleFilter={() => setShowOnlyMentions((v) => !v)}
                    mentionCount={data.mentioned_prompts.length}
                />
            </div>

            {/* ── Response Modal ───────────────────────────────────────────────── */}
            <AnimatePresence>
                {selectedResponse && (
                    <ResponseModal
                        text={selectedResponse.text}
                        platform={selectedResponse.platform}
                        onClose={() => setSelectedResponse(null)}
                    />
                )}
            </AnimatePresence>
        </div>
    );
}
