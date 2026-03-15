"use client";

import { motion } from "framer-motion";
import { CheckCircle, Building2, ArrowRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface BrandSelectorProps {
    brands: string[];
    selectedBrand: string | null;
    onSelect: (brand: string) => void;
    onConfirm: () => void;
    isLoading?: boolean;
}

export default function BrandSelector({
    brands,
    selectedBrand,
    onSelect,
    onConfirm,
    isLoading = false,
}: BrandSelectorProps) {
    const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

    const handleImageError = (brand: string) => {
        setImageErrors((prev) => new Set(prev).add(brand));
    };

    const getLogoUrl = (brand: string) => {
        const domain =
            brand
                .toLowerCase()
                .replace(/\s+/g, "")
                .replace(/[^a-z0-9]/g, "") + ".com";
        return `https://logo.clearbit.com/${domain}`;
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="w-full max-w-5xl mx-auto space-y-6"
        >
            {/* Header */}
            <div className="text-center space-y-2">
                <motion.h2
                    initial={{ y: -16, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="text-3xl font-black bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 bg-clip-text text-transparent"
                >
                    Select Your Brand
                </motion.h2>
                <p className="text-slate-500 dark:text-slate-400">
                    Choose the brand you want to track across AI platforms
                </p>
            </div>

            {/* Brand Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {brands.map((brand, index) => {
                    const isSelected = selectedBrand === brand;
                    const hasImageError = imageErrors.has(brand);

                    return (
                        <motion.button
                            key={brand}
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.04 }}
                            onClick={() => onSelect(brand)}
                            disabled={isLoading}
                            className={cn(
                                "relative group p-4 rounded-xl border-2 transition-all duration-200 text-left",
                                "hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2",
                                isSelected
                                    ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 shadow-md"
                                    : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-indigo-300 dark:hover:border-indigo-600"
                            )}
                        >
                            {/* Selection indicator */}
                            {isSelected && (
                                <motion.div
                                    initial={{ scale: 0 }}
                                    animate={{ scale: 1 }}
                                    className="absolute -top-2 -right-2 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-full p-1 shadow-lg"
                                >
                                    <CheckCircle className="w-4 h-4 text-white" />
                                </motion.div>
                            )}

                            <div className="flex items-center gap-3">
                                {/* Logo */}
                                <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden border border-slate-200 dark:border-slate-700">
                                    {!hasImageError ? (
                                        <img
                                            src={getLogoUrl(brand)}
                                            alt={`${brand} logo`}
                                            className="w-full h-full object-contain p-1.5"
                                            onError={() => handleImageError(brand)}
                                        />
                                    ) : (
                                        <Building2 className="w-6 h-6 text-slate-400" />
                                    )}
                                </div>

                                {/* Brand name */}
                                <div className="flex-1 min-w-0">
                                    <h3
                                        className={cn(
                                            "font-semibold text-base truncate transition-colors",
                                            isSelected
                                                ? "text-indigo-700 dark:text-indigo-400"
                                                : "text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400"
                                        )}
                                    >
                                        {brand}
                                    </h3>
                                </div>
                            </div>
                        </motion.button>
                    );
                })}
            </div>

            {/* Confirm Button */}
            <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="flex justify-center pt-2"
            >
                <button
                    onClick={onConfirm}
                    disabled={!selectedBrand || isLoading}
                    className={cn(
                        "group px-8 py-3.5 rounded-xl font-bold text-base transition-all duration-200 flex items-center gap-2.5",
                        selectedBrand && !isLoading
                            ? "bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 text-white hover:shadow-xl hover:scale-105 shadow-md"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
                    )}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            <span>Creating Campaign...</span>
                        </>
                    ) : (
                        <>
                            <span>Start Campaign</span>
                            <ArrowRight
                                className={cn(
                                    "w-5 h-5 transition-transform",
                                    selectedBrand && "group-hover:translate-x-1"
                                )}
                            />
                        </>
                    )}
                </button>
            </motion.div>
        </motion.div>
    );
}
