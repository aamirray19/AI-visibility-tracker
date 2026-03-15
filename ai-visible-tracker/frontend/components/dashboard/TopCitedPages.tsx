"use client";

import { motion } from "framer-motion";
import { ExternalLink, CheckCircle, Link } from "lucide-react";

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
    if (pages.length === 0) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white dark:bg-slate-900 rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-800"
        >
            <div className="mb-5">
                <h3 className="text-xl font-bold text-slate-900 dark:text-slate-50 flex items-center gap-2">
                    <Link className="w-5 h-5 text-indigo-500" />
                    Top Cited Pages
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Most frequently mentioned URLs in AI responses
                </p>
            </div>

            <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {pages.map((page, idx) => (
                    <motion.div
                        key={page.url}
                        initial={{ opacity: 0, x: -16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.04 }}
                        className="flex items-center gap-3 py-3 group"
                    >
                        {/* Rank */}
                        <div className="flex-shrink-0 w-7 text-center">
                            <span className="text-xs font-bold text-slate-400 dark:text-slate-500">
                                #{idx + 1}
                            </span>
                        </div>

                        {/* Favicon + domain link */}
                        <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden border border-slate-200 dark:border-slate-700">
                            <img
                                src={`https://www.google.com/s2/favicons?domain=${page.domain}&sz=32`}
                                alt=""
                                className="w-4 h-4 object-contain"
                                onError={(e) => {
                                    (e.target as HTMLImageElement).style.display = "none";
                                }}
                            />
                        </div>

                        {/* Domain + URL */}
                        <div className="flex-1 min-w-0">
                            <a
                                href={page.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1.5 text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 font-semibold text-sm group-hover:underline"
                            >
                                <span className="truncate">{page.domain}</span>
                                <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </a>
                            <div className="text-xs text-slate-400 dark:text-slate-500 truncate mt-0.5">
                                {page.url}
                            </div>
                        </div>

                        {/* Right side: count + badge */}
                        <div className="flex-shrink-0 flex items-center gap-2">
                            <div className="text-right">
                                <div className="text-sm font-bold text-slate-700 dark:text-slate-300">
                                    {page.mention_count}
                                </div>
                                <div className="text-xs text-slate-400 dark:text-slate-500">
                                    {page.mention_count === 1 ? "mention" : "mentions"}
                                </div>
                            </div>
                            {page.is_target_brand && (
                                <div className="flex items-center gap-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 rounded-full text-xs font-semibold border border-emerald-200 dark:border-emerald-800">
                                    <CheckCircle className="w-3 h-3" />
                                    Yours
                                </div>
                            )}
                        </div>
                    </motion.div>
                ))}
            </div>
        </motion.div>
    );
}
