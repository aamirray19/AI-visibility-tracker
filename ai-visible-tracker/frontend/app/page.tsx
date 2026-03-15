"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import CategoryInput from "@/components/setup/CategoryInput";
import BrandSelector from "@/components/setup/BrandSelector";
import ErrorToast from "@/components/ui/ErrorToast";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function Home() {
  const router = useRouter();
  const [step, setStep] = useState<"INPUT" | "SELECT">("INPUT");
  const [isLoading, setIsLoading] = useState(false);
  const [brands, setBrands] = useState<string[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [currentCategory, setCurrentCategory] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleDiscover = async (category: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/companies/discover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category }),
      });

      if (!response.ok) throw new Error("Failed to fetch brands");

      const data = await response.json();
      setBrands(data.brands);
      setCurrentCategory(category);
      setStep("SELECT");
    } catch {
      setError("Failed to load brands. Make sure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!selectedBrand) return;

    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/campaigns/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand: selectedBrand, category: currentCategory }),
      });

      if (!response.ok) throw new Error("Failed to create campaign");

      const data = await response.json();
      router.push(`/campaign/${data.id}`);
    } catch {
      setError("Failed to create campaign. Please try again.");
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setStep("INPUT");
    setSelectedBrand(null);
    setError(null);
  };

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col p-6 md:p-16 lg:p-24">
      {/* Error Toast */}
      <div className="w-full max-w-4xl mx-auto mb-4">
        <ErrorToast message={error} onDismiss={() => setError(null)} />
      </div>

      {/* Back Button (SELECT step only) */}
      {step === "SELECT" && (
        <div className="w-full max-w-5xl mx-auto mb-4">
          <button
            onClick={handleBack}
            className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        </div>
      )}

      {/* Steps */}
      {step === "INPUT" && (
        <div className="flex-1 flex flex-col justify-center">
          <CategoryInput onDiscover={handleDiscover} isLoading={isLoading} />
        </div>
      )}

      {step === "SELECT" && (
        <BrandSelector
          brands={brands}
          selectedBrand={selectedBrand}
          onSelect={setSelectedBrand}
          onConfirm={handleConfirm}
          isLoading={isLoading}
        />
      )}
    </main>
  );
}
