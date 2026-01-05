"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import CategoryInput from "@/components/setup/CategoryInput";
import BrandSelector from "@/components/setup/BrandSelector";

// Default API URL for development
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function Home() {
  const router = useRouter();
  const [appsState, setAppState] = useState<"INPUT" | "SELECT">("INPUT");
  const [isLoading, setIsLoading] = useState(false);
  const [brands, setBrands] = useState<string[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [currentCategory, setCurrentCategory] = useState("");

  const handleDiscover = async (category: string) => {
    setIsLoading(true);
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
      setAppState("SELECT");
    } catch (error) {
      console.error(error);
      alert("Failed to load brands. Make sure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!selectedBrand) return;

    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/campaigns/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brand: selectedBrand,
          category: currentCategory
        }),
      });

      if (!response.ok) throw new Error("Failed to create campaign");

      const data = await response.json();
      router.push(`/campaign/${data.id}`);
    } catch (error) {
      console.error(error);
      alert("Failed to create campaign.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-900 flex flex-col p-8 md:p-24">
      {appsState === "INPUT" && (
        <div className="flex-1 flex flex-col justify-center">
          <CategoryInput onDiscover={handleDiscover} isLoading={isLoading} />
        </div>
      )}

      {appsState === "SELECT" && (
        <BrandSelector
          brands={brands}
          selectedBrand={selectedBrand}
          onSelect={setSelectedBrand}
          onConfirm={handleConfirm}
        />
      )}
    </main>
  );
}
