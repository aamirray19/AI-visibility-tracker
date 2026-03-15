"use client";

import { motion } from "framer-motion";
import { TrendingUp, Link2, BarChart3, Heart } from "lucide-react";

interface AdvancedMetrics {
    ai_visibility: number;
    citation_share: number;
    average_rank: number;
    average_sentiment: number;
    total_mentions: number;
    total_citations: number;
}

interface MetricsGridProps {
    metrics: AdvancedMetrics;
}

export default function MetricsGrid({ metrics }: MetricsGridProps) {
    const cards = [
        {
            label: "AI Visibility",
            value: `${metrics.ai_visibility.toFixed(1)}%`,
            subtitle: `${metrics.total_mentions} mentions`,
            icon: TrendingUp,
            gradient: "from-indigo-500 to-purple-500",
            bgLight: "bg-indigo-50 dark:bg-indigo-950/30",
            border: "border-indigo-100 dark:border-indigo-900/50",
        },
        {
            label: "Citation Share",
            value: `${metrics.citation_share.toFixed(1)}%`,
            subtitle: `${metrics.total_citations} citations`,
            icon: Link2,
            gradient: "from-blue-500 to-cyan-500",
            bgLight: "bg-blue-50 dark:bg-blue-950/30",
            border: "border-blue-100 dark:border-blue-900/50",
        },
        {
            label: "Average Rank",
            value: metrics.average_rank > 0 ? `#${metrics.average_rank.toFixed(1)}` : "—",
            subtitle: "Position in results",
            icon: BarChart3,
            gradient: "from-emerald-500 to-teal-500",
            bgLight: "bg-emerald-50 dark:bg-emerald-950/30",
            border: "border-emerald-100 dark:border-emerald-900/50",
        },
        {
            label: "Sentiment",
            value: `${(metrics.average_sentiment * 100).toFixed(0)}%`,
            subtitle: "Overall positivity",
            icon: Heart,
            gradient: "from-rose-500 to-pink-500",
            bgLight: "bg-rose-50 dark:bg-rose-950/30",
            border: "border-rose-100 dark:border-rose-900/50",
        },
    ];

    return (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {cards.map((card, idx) => (
                <motion.div
                    key={card.label}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.08 }}
                    className={`rounded-2xl p-5 shadow-sm border transition-shadow hover:shadow-md ${card.bgLight} ${card.border}`}
                >
                    {/* Icon + Label */}
                    <div className="flex items-center gap-2.5 mb-4">
                        <div className={`bg-gradient-to-br ${card.gradient} p-2 rounded-lg flex-shrink-0`}>
                            <card.icon className="w-4 h-4 text-white" />
                        </div>
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide leading-tight">
                            {card.label}
                        </span>
                    </div>

                    {/* Value */}
                    <div className={`text-3xl font-black bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent mb-1`}>
                        {card.value}
                    </div>

                    {/* Subtitle */}
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">{card.subtitle}</p>
                </motion.div>
            ))}
        </div>
    );
}
