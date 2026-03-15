"use client";

import { motion } from "framer-motion";
import { Bot, Cpu, TrendingUp, BarChart3, Heart, Award } from "lucide-react";

interface ModelMetrics {
    platform: string;
    ai_visibility: number;
    average_rank: number;
    average_sentiment: number;
    total_mentions: number;
    total_results: number;
}

interface ModelComparisonPanelProps {
    perModelMetrics: ModelMetrics[];
}

const MODEL_CONFIG: Record<string, { label: string; icon: typeof Bot; color: string; gradient: string; bgDark: string; border: string; }> = {
    gpt: {
        label: "GPT-OSS-120B",
        icon: Bot,
        color: "text-emerald-600 dark:text-emerald-400",
        gradient: "from-emerald-500 to-teal-500",
        bgDark: "bg-emerald-50 dark:bg-emerald-950/30",
        border: "border-emerald-100 dark:border-emerald-900/50",
    },
    gemma: {
        label: "Gemma3:27B",
        icon: Cpu,
        color: "text-blue-600 dark:text-blue-400",
        gradient: "from-blue-500 to-indigo-500",
        bgDark: "bg-blue-50 dark:bg-blue-950/30",
        border: "border-blue-100 dark:border-blue-900/50",
    },
};

function StatRow({ icon: Icon, label, value, gradient }: { icon: typeof TrendingUp; label: string; value: string; gradient: string }) {
    return (
        <div className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-800 last:border-0">
            <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                <Icon className="w-3.5 h-3.5" />
                {label}
            </div>
            <span className={`text-sm font-bold bg-gradient-to-r ${gradient} bg-clip-text text-transparent`}>
                {value}
            </span>
        </div>
    );
}

export default function ModelComparisonPanel({ perModelMetrics }: ModelComparisonPanelProps) {
    if (!perModelMetrics || perModelMetrics.length === 0) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white dark:bg-slate-900 rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800"
        >
            <div className="mb-5">
                <h3 className="text-xl font-bold text-slate-900 dark:text-slate-50 flex items-center gap-2">
                    <Award className="w-5 h-5 text-purple-500" />
                    Model Comparison
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Side-by-side results from each AI model
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {perModelMetrics.map((model, idx) => {
                    const config = MODEL_CONFIG[model.platform] ?? {
                        label: model.platform.toUpperCase(),
                        icon: Bot,
                        color: "text-slate-600",
                        gradient: "from-slate-500 to-slate-600",
                        bgDark: "bg-slate-50 dark:bg-slate-800",
                        border: "border-slate-200 dark:border-slate-700",
                    };
                    const Icon = config.icon;

                    return (
                        <motion.div
                            key={model.platform}
                            initial={{ opacity: 0, scale: 0.97 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: idx * 0.1 }}
                            className={`rounded-xl p-4 border ${config.bgDark} ${config.border}`}
                        >
                            {/* Model Header */}
                            <div className="flex items-center gap-2.5 mb-4">
                                <div className={`bg-gradient-to-br ${config.gradient} p-1.5 rounded-lg`}>
                                    <Icon className="w-4 h-4 text-white" />
                                </div>
                                <div>
                                    <div className={`font-bold text-sm ${config.color}`}>{config.label}</div>
                                    <div className="text-xs text-slate-400 dark:text-slate-500">
                                        {model.total_results} responses
                                    </div>
                                </div>
                            </div>

                            {/* Stats */}
                            <div>
                                <StatRow
                                    icon={TrendingUp}
                                    label="AI Visibility"
                                    value={`${model.ai_visibility.toFixed(1)}%`}
                                    gradient={config.gradient}
                                />
                                <StatRow
                                    icon={BarChart3}
                                    label="Avg. Rank"
                                    value={model.average_rank > 0 ? `#${model.average_rank.toFixed(1)}` : "—"}
                                    gradient={config.gradient}
                                />
                                <StatRow
                                    icon={Heart}
                                    label="Sentiment"
                                    value={`${(model.average_sentiment * 100).toFixed(0)}%`}
                                    gradient={config.gradient}
                                />
                                <StatRow
                                    icon={Award}
                                    label="Mentions"
                                    value={`${model.total_mentions}`}
                                    gradient={config.gradient}
                                />
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </motion.div>
    );
}
