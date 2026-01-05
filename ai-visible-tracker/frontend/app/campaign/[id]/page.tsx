"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle, Clock, Activity, Zap, Filter } from "lucide-react";
import { clsx } from "clsx";
import { motion, AnimatePresence } from "framer-motion";
import MetricsGrid from "@/components/dashboard/MetricsGrid";
import CompetitorLeaderboard from "@/components/dashboard/CompetitorLeaderboard";
import TopCitedPages from "@/components/dashboard/TopCitedPages";

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

interface CampaignDashboard {
    id: number;
    brand: string;
    total_prompts: number;
    processed_count: number;
    metrics: AdvancedMetrics;
    competitors: CompetitorStats[];
    top_cited_pages: CitedPage[];
    mentioned_prompts: PromptResult[];
    results: PromptResult[];
}

export default function CampaignDashboardPage() {
    const params = useParams();
    const [data, setData] = useState<CampaignDashboard | null>(null);
    const [loading, setLoading] = useState(true);
    const [selectedResponse, setSelectedResponse] = useState<string | null>(null);
    const [showOnlyMentions, setShowOnlyMentions] = useState(false);
    const [recentActivity, setRecentActivity] = useState<PromptResult[]>([]);

    // Poll for updates every 3 seconds
    useEffect(() => {
        const fetchData = async () => {
            try {
                const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'}/campaigns/${params.id}`);
                if (res.ok) {
                    const json = await res.json();

                    // Track newly completed items for activity feed
                    if (data) {
                        const newCompleted = json.results.filter((r: PromptResult) =>
                            r.status === "COMPLETED" &&
                            !data.results.find(old => old.id === r.id && old.status === "COMPLETED")
                        );
                        if (newCompleted.length > 0) {
                            setRecentActivity(prev => [...newCompleted.slice(0, 3), ...prev].slice(0, 5));
                        }
                    }

                    setData(json);
                }
            } catch (error) {
                console.error("Failed to fetch dashboard", error);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 3000);
        return () => clearInterval(interval);
    }, [params.id, data]);

    if (loading && !data) return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
            <div className="text-center space-y-4">
                <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-slate-600 font-medium">Loading Campaign...</p>
            </div>
        </div>
    );

    if (!data) return <div className="p-10 text-center text-red-500">Campaign not found</div>;

    const progressPercentage = (data.processed_count / data.total_prompts) * 100;
    const isComplete = data.processed_count === data.total_prompts;
    const displayResults = showOnlyMentions ? data.mentioned_prompts : data.results;

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-purple-50/30 p-8">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header with Brand Name */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-5xl font-black bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 bg-clip-text text-transparent">
                            {data.brand}
                        </h1>
                        <p className="text-slate-600 mt-2 text-lg">Campaign Analytics Dashboard</p>
                    </div>
                    {isComplete && (
                        <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            className="flex items-center gap-2 bg-emerald-100 text-emerald-700 px-5 py-3 rounded-full font-bold text-lg"
                        >
                            <CheckCircle className="w-6 h-6" />
                            Complete
                        </motion.div>
                    )}
                </div>

                {/* Progress Bar Section */}
                {!isComplete && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200"
                    >
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-2 rounded-lg">
                                    <Activity className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h3 className="font-bold text-lg text-slate-900">Processing Progress</h3>
                                    <p className="text-sm text-slate-500">
                                        {data.processed_count} of {data.total_prompts} prompts analyzed
                                    </p>
                                </div>
                            </div>
                            <div className="text-right">
                                <div className="text-3xl font-black bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                                    {progressPercentage.toFixed(1)}%
                                </div>
                            </div>
                        </div>

                        {/* Animated Progress Bar */}
                        <div className="relative h-4 bg-slate-100 rounded-full overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${progressPercentage}%` }}
                                transition={{ duration: 0.5, ease: "easeOut" }}
                                className="absolute inset-y-0 left-0 bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 rounded-full"
                            />
                            <motion.div
                                animate={{ x: ["-100%", "400%"] }}
                                transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                            />
                        </div>

                        <div className="mt-3 flex items-center gap-2 text-sm">
                            <Zap className="w-4 h-4 text-yellow-500 animate-pulse" />
                            <span className="text-slate-600 font-medium">
                                Processing in real-time...
                            </span>
                        </div>
                    </motion.div>
                )}

                {/* Metrics Grid */}
                <MetricsGrid metrics={data.metrics} />

                {/* Competitor Leaderboard */}
                {data.competitors.length > 0 && (
                    <CompetitorLeaderboard
                        competitors={data.competitors}
                        targetBrand={data.brand}
                    />
                )}

                {/* Top Cited Pages */}
                {data.top_cited_pages.length > 0 && (
                    <TopCitedPages pages={data.top_cited_pages} />
                )}

                {/* Activity Feed */}
                {recentActivity.length > 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200"
                    >
                        <h3 className="font-bold text-lg text-slate-900 mb-4 flex items-center gap-2">
                            <Zap className="w-5 h-5 text-yellow-500" />
                            Recent Activity
                        </h3>
                        <div className="space-y-3">
                            <AnimatePresence>
                                {recentActivity.map((item, index) => (
                                    <motion.div
                                        key={item.id}
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: 20 }}
                                        transition={{ delay: index * 0.1 }}
                                        className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200"
                                    >
                                        <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-slate-900 truncate">
                                                {item.text}
                                            </p>
                                            <div className="flex items-center gap-3 mt-1">
                                                <span className="text-xs text-slate-500">
                                                    Rank: {item.rank ? `#${item.rank}` : 'Not mentioned'}
                                                </span>
                                                {item.sentiment !== null && (
                                                    <span className="text-xs text-slate-500">
                                                        Sentiment: {(item.sentiment * 100).toFixed(0)}%
                                                    </span>
                                                )}
                                                <span className="text-xs text-indigo-600 font-semibold uppercase">
                                                    {item.platform}
                                                </span>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                )}

                {/* Results Table */}
                <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
                    <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                        <div>
                            <h2 className="text-xl font-bold text-slate-800">
                                {showOnlyMentions ? 'Brand Mentions' : 'All Results'}
                            </h2>
                            <p className="text-sm text-slate-500 mt-1">
                                {showOnlyMentions
                                    ? `${data.mentioned_prompts.length} prompts where ${data.brand} was mentioned`
                                    : 'Detailed breakdown of each query'
                                }
                            </p>
                        </div>

                        {/* Filter Toggle */}
                        <button
                            onClick={() => setShowOnlyMentions(!showOnlyMentions)}
                            className={clsx(
                                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all",
                                showOnlyMentions
                                    ? "bg-indigo-600 text-white shadow-lg"
                                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                            )}
                        >
                            <Filter className="w-4 h-4" />
                            {showOnlyMentions ? 'Show All' : 'Show Mentions Only'}
                        </button>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">
                                <tr>
                                    <th className="px-6 py-4 font-medium">Prompt</th>
                                    <th className="px-6 py-4 font-medium">Intent</th>
                                    <th className="px-6 py-4 font-medium">Status</th>
                                    <th className="px-6 py-4 font-medium">Rank</th>
                                    <th className="px-6 py-4 font-medium">Sentiment</th>
                                    <th className="px-6 py-4 font-medium">Platform</th>
                                    <th className="px-6 py-4 font-medium text-right">Response</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {displayResults.map((result) => (
                                    <tr key={result.id} className="hover:bg-slate-50/50 transition-colors">
                                        <td className="px-6 py-4 text-slate-900 font-medium max-w-md truncate">{result.text}</td>
                                        <td className="px-6 py-4">
                                            <span className={clsx(
                                                "px-2 py-1 rounded-full text-xs font-semibold",
                                                result.intent === "commercial" ? "bg-blue-100 text-blue-700" : "bg-purple-100 text-purple-700"
                                            )}>
                                                {result.intent}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            {result.status === "COMPLETED" ? (
                                                <div className="flex items-center text-emerald-600 text-sm">
                                                    <CheckCircle className="w-4 h-4 mr-2" />
                                                    Done
                                                </div>
                                            ) : (
                                                <div className="flex items-center text-amber-500 text-sm">
                                                    <Clock className="w-4 h-4 mr-2 animate-pulse" />
                                                    Processing...
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {result.rank ? (
                                                <span className="text-lg font-bold text-slate-800">#{result.rank}</span>
                                            ) : (
                                                <span className="text-slate-400">-</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {result.sentiment !== null ? (
                                                <div className="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                                                    <div
                                                        className={clsx("h-full", result.sentiment > 0.6 ? "bg-emerald-500" : result.sentiment < 0.4 ? "bg-red-500" : "bg-amber-400")}
                                                        style={{ width: `${result.sentiment * 100}%` }}
                                                    />
                                                </div>
                                            ) : (
                                                <span className="text-slate-400">-</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="uppercase text-xs font-bold text-slate-500">{result.platform}</span>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            {result.response_text ? (
                                                <button
                                                    onClick={() => setSelectedResponse(result.response_text)}
                                                    className="text-indigo-600 hover:text-indigo-800 font-medium text-sm border border-indigo-200 px-3 py-1 rounded hover:bg-indigo-50 transition-colors"
                                                >
                                                    View Text
                                                </button>
                                            ) : (
                                                <span className="text-slate-300 text-sm">...</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Response Modal */}
                {selectedResponse && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setSelectedResponse(null)}>
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            onClick={(e) => e.stopPropagation()}
                            className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col"
                        >
                            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                                <h3 className="font-bold text-xl text-slate-900">AI Response</h3>
                                <button
                                    onClick={() => setSelectedResponse(null)}
                                    className="text-slate-400 hover:text-slate-600 transition-colors"
                                >
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                            <div className="p-6 overflow-y-auto whitespace-pre-wrap font-mono text-sm text-slate-700 bg-slate-50">
                                {selectedResponse}
                            </div>
                        </motion.div>
                    </div>
                )}
            </div>
        </div>
    );
}
