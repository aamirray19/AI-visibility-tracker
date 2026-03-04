"use client";

import { useState } from "react";
import { Search, Loader2, Sparkles, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/utils/cn";

interface CategoryInputProps {
    onDiscover: (category: string) => void;
    isLoading: boolean;
}

export default function CategoryInput({ onDiscover, isLoading }: CategoryInputProps) {
    const [category, setCategory] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (category.trim()) {
            onDiscover(category);
        }
    };

    return (
        <div className="relative w-full max-w-4xl mx-auto">
            {/* Animated gradient background orbs */}
            <div className="absolute inset-0 -z-10 overflow-hidden">
                <motion.div
                    animate={{
                        scale: [1, 1.2, 1],
                        opacity: [0.3, 0.5, 0.3],
                    }}
                    transition={{
                        duration: 8,
                        repeat: Infinity,
                        ease: "easeInOut"
                    }}
                    className="absolute -top-40 -left-40 w-96 h-96 bg-gradient-to-br from-indigo-400 to-purple-600 rounded-full blur-3xl"
                />
                <motion.div
                    animate={{
                        scale: [1.2, 1, 1.2],
                        opacity: [0.3, 0.5, 0.3],
                    }}
                    transition={{
                        duration: 10,
                        repeat: Infinity,
                        ease: "easeInOut"
                    }}
                    className="absolute -bottom-40 -right-40 w-96 h-96 bg-gradient-to-br from-blue-400 to-cyan-600 rounded-full blur-3xl"
                />
            </div>

            <motion.div
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="space-y-8"
            >
                {/* Logo and Branding */}
                <div className="text-center space-y-4">
                    <motion.div
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ delay: 0.2, duration: 0.5 }}
                        className="inline-flex items-center gap-3 mb-4"
                    >
                        <div className="relative">
                            <div className="absolute inset-0 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl blur-xl opacity-60" />
                            <div className="relative bg-gradient-to-br from-indigo-600 via-purple-600 to-blue-600 p-3 rounded-2xl shadow-2xl">
                                <TrendingUp className="w-8 h-8 text-white" strokeWidth={2.5} />
                            </div>
                        </div>
                        <h1 className="text-6xl font-black bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 bg-clip-text text-transparent tracking-tight">
                            BrandSight AI
                        </h1>
                    </motion.div>

                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.4 }}
                        className="text-xl text-slate-600 dark:text-slate-300 font-medium max-w-2xl mx-auto"
                    >
                        Track your brand visibility across AI platforms in real-time
                    </motion.p>

                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                        className="flex items-center justify-center gap-2 text-sm text-slate-500"
                    >
                        <Sparkles className="w-4 h-4 text-yellow-500" />
                        <span>Powered by Advanced AI Analysis</span>
                    </motion.div>
                </div>

                {/* Input Section */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.6 }}
                    className="relative"
                >
                    {/* Glassmorphism card */}
                    <div className="relative bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/20 dark:border-slate-700/50">
                        <div className="space-y-4">
                            <div className="text-center">
                                <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50 mb-2">
                                    Start Your Campaign
                                </h2>
                                <p className="text-slate-600 dark:text-slate-400">
                                    Enter your product category to discover competing brands
                                </p>
                            </div>

                            <form onSubmit={handleSubmit} className="relative">
                                <div className="relative group">
                                    <div className="absolute -inset-1 bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-300" />
                                    <div className="relative flex items-center">
                                        <Search className="absolute left-6 text-slate-400 w-6 h-6 z-10" />
                                        <input
                                            type="text"
                                            value={category}
                                            onChange={(e) => setCategory(e.target.value)}
                                            disabled={isLoading}
                                            placeholder="e.g. Running Shoes, CRM Software, Coffee Machines..."
                                            className="w-full pl-16 pr-36 py-5 rounded-2xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 shadow-lg focus:ring-4 focus:ring-indigo-500/20 focus:border-indigo-500 focus:outline-none transition-all text-lg font-medium placeholder:text-slate-400"
                                        />
                                        <button
                                            type="submit"
                                            disabled={isLoading || !category.trim()}
                                            className={cn(
                                                "absolute right-2 px-8 py-3 rounded-xl font-bold transition-all duration-300 flex items-center gap-2",
                                                isLoading || !category.trim()
                                                    ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                                                    : "bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 text-white hover:shadow-2xl hover:scale-105 shadow-lg"
                                            )}
                                        >
                                            {isLoading ? (
                                                <>
                                                    <Loader2 className="w-5 h-5 animate-spin" />
                                                    <span>Analyzing...</span>
                                                </>
                                            ) : (
                                                <>
                                                    <Sparkles className="w-5 h-5" />
                                                    <span>Discover</span>
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </form>

                            {/* Feature highlights */}
                            <div className="grid grid-cols-3 gap-4 pt-6 border-t border-slate-200 dark:border-slate-700">
                                <div className="text-center">
                                    <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">100+</div>
                                    <div className="text-xs text-slate-600 dark:text-slate-400">AI Queries</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">Real-time</div>
                                    <div className="text-xs text-slate-600 dark:text-slate-400">Analysis</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">Instant</div>
                                    <div className="text-xs text-slate-600 dark:text-slate-400">Insights</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </motion.div>
            </motion.div>
        </div>
    );
}
