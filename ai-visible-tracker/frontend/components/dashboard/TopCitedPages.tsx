"use client";

import { motion } from "framer-motion";
import { ExternalLink, CheckCircle } from "lucide-react";

interface CitedPage {
    url: string;
    domain: string;
    mention_count: number;
    is_target_brand: boolean;
}

interface TopCitedPagesProps {
    pages: CitedPage[];
}

export default function TopCitedPages({ pages }: TopCitedPagesProps) {
    if (pages.length === 0) {
        return null;
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200"
        >
            <div className="mb-6">
                <h3 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                    <span className="text-3xl">🔗</span>
                    Top Cited Pages
                </h3>
                <p className="text-slate-600 mt-1">Most frequently mentioned URLs in AI responses</p>
            </div>

            <div className="space-y-2">
                {pages.map((page, idx) => (
                    <motion.div
                        key={page.url}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        className="flex items-center gap-3 p-3 hover:bg-slate-50 rounded-lg transition-colors group"
                    >
                        {/* Rank Number */}
                        <div className="flex-shrink-0 w-8 text-center">
                            <div className="font-bold text-slate-400 text-lg">
                                #{idx + 1}
                            </div>
                        </div>

                        {/* URL/Domain */}
                        <div className="flex-1 min-w-0">
                            <a
                                href={page.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-2 text-indigo-600 hover:text-indigo-800 font-medium group-hover:underline"
                            >
                                <span className="truncate">{page.domain}</span>
                                <ExternalLink className="w-4 h-4 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </a>
                            <div className="text-xs text-slate-500 truncate mt-0.5">
                                {page.url}
                            </div>
                        </div>

                        {/* Mention Count */}
                        <div className="flex-shrink-0 flex items-center gap-3">
                            <div className="text-right">
                                <div className="font-bold text-slate-700">
                                    {page.mention_count}
                                </div>
                                <div className="text-xs text-slate-500">
                                    {page.mention_count === 1 ? 'mention' : 'mentions'}
                                </div>
                            </div>

                            {/* Your Brand Badge */}
                            {page.is_target_brand && (
                                <div className="flex items-center gap-1 bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full text-xs font-bold">
                                    <CheckCircle className="w-3 h-3" />
                                    Your Brand
                                </div>
                            )}
                        </div>
                    </motion.div>
                ))}
            </div>

            {pages.length === 0 && (
                <div className="text-center py-8 text-slate-400">
                    <p>No URLs cited in responses</p>
                </div>
            )}
        </motion.div>
    );
}
