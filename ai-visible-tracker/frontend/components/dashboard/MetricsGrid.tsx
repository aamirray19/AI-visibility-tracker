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
            color: "indigo",
            gradient: "from-indigo-500 to-purple-500"
        },
        {
            label: "Citation Share",
            value: `${metrics.citation_share.toFixed(1)}%`,
            subtitle: `${metrics.total_citations} citations`,
            icon: Link2,
            color: "blue",
            gradient: "from-blue-500 to-cyan-500"
        },
        {
            label: "Average Rank",
            value: metrics.average_rank > 0 ? `#${metrics.average_rank.toFixed(1)}` : '-',
            subtitle: "Position in results",
            icon: BarChart3,
            color: "emerald",
            gradient: "from-emerald-500 to-teal-500"
        },
        {
            label: "Sentiment",
            value: `${(metrics.average_sentiment * 100).toFixed(0)}%`,
            subtitle: "Overall positivity",
            icon: Heart,
            color: "rose",
            gradient: "from-rose-500 to-pink-500"
        }
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {cards.map((card, idx) => (
                <motion.div
                    key={card.label}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200 hover:shadow-xl transition-shadow"
                >
                    {/* Icon */}
                    <div className="flex items-center gap-3 mb-3">
                        <div className={`bg-gradient-to-br ${card.gradient} p-2.5 rounded-xl`}>
                            <card.icon className="w-5 h-5 text-white" />
                        </div>
                        <span className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                            {card.label}
                        </span>
                    </div>

                    {/* Value */}
                    <div className={`text-4xl font-black bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent mb-1`}>
                        {card.value}
                    </div>

                    {/* Subtitle */}
                    <p className="text-xs text-slate-500 font-medium">
                        {card.subtitle}
                    </p>
                </motion.div>
            ))}
        </div>
    );
}
