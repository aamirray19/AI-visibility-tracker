"use client";

import { motion } from "framer-motion";
import { Trophy } from "lucide-react";

interface CompetitorStats {
    name: string;
    mention_count: number;
    ai_visibility: number;
    average_rank: number;
    average_sentiment: number;
}

interface CompetitorLeaderboardProps {
    competitors: CompetitorStats[];
    targetBrand: string;
}

export default function CompetitorLeaderboard({ competitors }: CompetitorLeaderboardProps) {
    if (competitors.length === 0) return null;

    const medals = ["🥇", "🥈", "🥉"];
    const maxVisibility = Math.max(...competitors.map((c) => c.ai_visibility), 1);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white dark:bg-slate-900 rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800"
        >
            <div className="mb-5">
                <h3 className="text-xl font-bold text-slate-900 dark:text-slate-50 flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-amber-500" />
                    Competitor Leaderboard
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    How you stack up against the competition
                </p>
            </div>

            <div className="space-y-3">
                {competitors.map((comp, idx) => (
                    <motion.div
                        key={comp.name}
                        initial={{ opacity: 0, x: -16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.06 }}
                        className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-100 dark:border-slate-700/50 hover:shadow-sm transition-shadow"
                    >
                        {/* Rank */}
                        <div className="flex-shrink-0 w-10 text-center">
                            {idx < 3 ? (
                                <span className="text-2xl">{medals[idx]}</span>
                            ) : (
                                <span className="text-base font-bold text-slate-400 dark:text-slate-500">
                                    #{idx + 1}
                                </span>
                            )}
                        </div>

                        {/* Brand + Progress */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1.5">
                                <span className="font-semibold text-slate-900 dark:text-slate-100 truncate">
                                    {comp.name}
                                </span>
                                <span className="text-sm font-bold text-indigo-600 dark:text-indigo-400 ml-2 flex-shrink-0">
                                    {comp.ai_visibility.toFixed(1)}%
                                </span>
                            </div>
                            {/* Visibility bar */}
                            <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                <motion.div
                                    initial={{ width: 0 }}
                                    animate={{ width: `${(comp.ai_visibility / maxVisibility) * 100}%` }}
                                    transition={{ duration: 0.6, delay: idx * 0.06 }}
                                    className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full"
                                />
                            </div>
                            <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                                <span>{comp.mention_count} mentions</span>
                                <span>·</span>
                                <span>Rank #{comp.average_rank.toFixed(1)}</span>
                                <span>·</span>
                                <span>{(comp.average_sentiment * 100).toFixed(0)}% sentiment</span>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>
        </motion.div>
    );
}
