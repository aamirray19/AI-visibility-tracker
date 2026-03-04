"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { CheckCircle, Building2, ArrowRight } from "lucide-react";
import { cn } from "@/utils/cn";
import { useState } from "react";

interface BrandSelectorProps {
    brands: string[];
    selectedBrand: string | null;
    onSelect: (brand: string) => void;
    onConfirm: () => void;
}

export default function BrandSelector({
    brands,
    selectedBrand,
    onSelect,
    onConfirm,
}: BrandSelectorProps) {
    const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

    const handleImageError = (brand: string) => {
        setImageErrors(prev => new Set(prev).add(brand));
    };

    const getLogoUrl = (brand: string) => {
        // Use Clearbit Logo API - free tier available
        // Format: https://logo.clearbit.com/{domain}
        // We'll try to guess the domain from the brand name
        const domain = brand.toLowerCase()
            .replace(/\s+/g, '')
            .replace(/[^a-z0-9]/g, '') + '.com';
        return `https://logo.clearbit.com/${domain}`;
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="w-full max-w-6xl mx-auto space-y-6"
        >
            {/* Header */}
            <div className="text-center space-y-2">
                <motion.h2
                    initial={{ y: -20, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    className="text-4xl font-bold bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 bg-clip-text text-transparent"
                >
                    Select Your Brand
                </motion.h2>
                <p className="text-slate-600 dark:text-slate-400 text-lg">
                    Choose the brand you want to track across AI platforms
                </p>
            </div>

            {/* Brand Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {brands.map((brand, index) => {
                    const isSelected = selectedBrand === brand;
                    const hasImageError = imageErrors.has(brand);

                    return (
                        <motion.button
                            key={brand}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.05 }}
                            onClick={() => onSelect(brand)}
                            className={cn(
                                "relative group p-6 rounded-2xl border-2 transition-all duration-300 text-left",
                                "hover:shadow-xl hover:scale-105",
                                isSelected
                                    ? "border-indigo-500 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950/30 dark:to-purple-950/30 shadow-lg"
                                    : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-indigo-300"
                            )}
                        >
                            {/* Selection indicator */}
                            {isSelected && (
                                <motion.div
                                    initial={{ scale: 0 }}
                                    animate={{ scale: 1 }}
                                    className="absolute -top-2 -right-2 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-full p-1.5 shadow-lg"
                                >
                                    <CheckCircle className="w-5 h-5 text-white" />
                                </motion.div>
                            )}

                            {/* Gradient border effect on hover */}
                            <div className={cn(
                                "absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300",
                                "bg-gradient-to-r from-indigo-500 via-purple-500 to-blue-500 blur-xl -z-10",
                                isSelected && "opacity-50"
                            )} />

                            <div className="flex items-center gap-4">
                                {/* Logo */}
                                <div className="flex-shrink-0 w-16 h-16 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center overflow-hidden border border-slate-200 dark:border-slate-700">
                                    {!hasImageError ? (
                                        <Image
                                            src={getLogoUrl(brand)}
                                            alt={`${brand} logo`}
                                            width={64}
                                            height={64}
                                            className="w-full h-full object-contain p-2"
                                            onError={() => handleImageError(brand)}
                                        />
                                    ) : (
                                        <Building2 className="w-8 h-8 text-slate-400" />
                                    )}
                                </div>

                                {/* Brand name */}
                                <div className="flex-1 min-w-0">
                                    <h3 className={cn(
                                        "font-bold text-lg truncate transition-colors",
                                        isSelected
                                            ? "text-indigo-700 dark:text-indigo-400"
                                            : "text-slate-900 dark:text-slate-100 group-hover:text-indigo-600"
                                    )}>
                                        {brand}
                                    </h3>
                                    <p className="text-sm text-slate-500 dark:text-slate-400">
                                        Click to select
                                    </p>
                                </div>
                            </div>
                        </motion.button>
                    );
                })}
            </div>

            {/* Confirm Button */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="flex justify-center pt-4"
            >
                <button
                    onClick={onConfirm}
                    disabled={!selectedBrand}
                    className={cn(
                        "group px-10 py-4 rounded-2xl font-bold text-lg transition-all duration-300 flex items-center gap-3",
                        selectedBrand
                            ? "bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-600 text-white hover:shadow-2xl hover:scale-105 shadow-lg"
                            : "bg-slate-200 text-slate-400 cursor-not-allowed"
                    )}
                >
                    <span>Start Campaign</span>
                    <ArrowRight className={cn(
                        "w-6 h-6 transition-transform",
                        selectedBrand && "group-hover:translate-x-1"
                    )} />
                </button>
            </motion.div>
        </motion.div>
    );
}
