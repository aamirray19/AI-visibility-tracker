"use client";

import { motion } from "framer-motion";

interface CompetitorStats {
    name: string;
    mention_count: number;
    ai_visibility: number;
    average_rank: number;
    average_sentiment: number;
}

interface CompetitorLeaderboardProps {
    competitors: CompetitorStats[];
}

export default function CompetitorLeaderboard({ competitors }: CompetitorLeaderboardProps) {
    if (competitors.length === 0) {
        return null;
    }

    const medals = ['🥇', '🥈', '🥉'];

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200"
        >
            <div className="mb-6">
                <h3 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                    <span className="text-3xl">🏆</span>
                    Competitor Leaderboard
                </h3>
                <p className="text-slate-600 mt-1">How you stack up against the competition</p>
            </div>

            <div className="space-y-3">
                {competitors.map((comp, idx) => (
                    <motion.div
                        key={comp.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.1 }}
                        className="flex items-center gap-4 p-4 bg-gradient-to-r from-slate-50 to-white rounded-xl border border-slate-200 hover:shadow-md transition-shadow"
                    >
                        {/* Rank Medal/Number */}
                        <div className="flex-shrink-0 w-12 text-center">
                            <div className="text-4xl">
                                {idx < 3 ? medals[idx] : `#${idx + 1}`}
                            </div>
                        </div>

                        {/* Brand Name */}
                        <div className="flex-1 min-w-0">
                            <div className="font-bold text-lg text-slate-900 truncate">
                                {comp.name}
                            </div>
                            <div className="flex items-center gap-4 mt-1 text-sm text-slate-600">
                                <span>{comp.mention_count} mentions</span>
                                <span>•</span>
                                <span>Rank #{comp.average_rank.toFixed(1)}</span>
                                <span>•</span>
                                <span>{(comp.average_sentiment * 100).toFixed(0)}% sentiment</span>
                            </div>
                        </div>

                        {/* AI Visibility Score */}
                        <div className="flex-shrink-0 text-right">
                            <div className="text-3xl font-black bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                                {comp.ai_visibility.toFixed(1)}%
                            </div>
                            <div className="text-xs text-slate-500 font-medium">AI Visibility</div>
                        </div>
                    </motion.div>
                ))}
            </div>

            {competitors.length === 0 && (
                <div className="text-center py-8 text-slate-400">
                    <p>No competitors detected in responses</p>
                </div>
            )}
        </motion.div>
    );
}
