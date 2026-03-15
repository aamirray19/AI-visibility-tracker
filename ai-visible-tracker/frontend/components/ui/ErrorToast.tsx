"use client";

import { AlertCircle, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ErrorToastProps {
    message: string | null;
    onDismiss: () => void;
}

export default function ErrorToast({ message, onDismiss }: ErrorToastProps) {
    return (
        <AnimatePresence>
            {message && (
                <motion.div
                    initial={{ opacity: 0, y: -16, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -16, scale: 0.97 }}
                    transition={{ duration: 0.25 }}
                    className="flex items-start gap-3 px-4 py-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 rounded-xl shadow-md"
                >
                    <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                    <p className="flex-1 text-sm font-medium">{message}</p>
                    <button
                        onClick={onDismiss}
                        className="text-red-400 hover:text-red-600 dark:hover:text-red-300 transition-colors flex-shrink-0"
                        aria-label="Dismiss error"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
