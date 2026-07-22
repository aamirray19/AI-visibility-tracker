// Hand-written mirrors of the FastAPI response shapes (§4/§6/§12). No
// codegen -- there's no OpenAPI spec to generate from, so these are kept in
// sync by hand whenever a backend response_model changes.

export type ScanStatus =
  | "created"
  | "enriching"
  | "awaiting_verification"
  | "verifying"
  | "scope_pending"
  | "queued"
  | "generating_prompts"
  | "executing"
  | "evaluating"
  | "aggregating"
  | "completed"
  | "completed_with_gaps"
  | "failed"
  | "cancelled";

export const MONITORING_CATEGORIES = [
  "brand_mentions",
  "product_recommendations",
  "competitor_comparisons",
  "purchase_intent",
  "feature_comparisons",
  "alternatives",
  "reviews",
  "pricing_discussions",
  "technical_evaluations",
] as const;
export type MonitoringCategory = (typeof MONITORING_CATEGORIES)[number];

export const ERROR_CODES = [
  "INVALID_WEBSITE",
  "COMPANY_MISMATCH",
  "ENRICHMENT_LOW_CONFIDENCE",
  "INVALID_STATE_TRANSITION",
  "PROVIDER_UNAVAILABLE",
  "SCAN_FAILED",
  "RATE_LIMITED",
  "COST_CEILING_EXCEEDED",
  "UNAUTHORIZED",
] as const;
export type ErrorCode = (typeof ERROR_CODES)[number] | "UNKNOWN_ERROR";

export interface ResolveCompanyResponse {
  company_id: string;
  name: string;
  domain: string;
  recent_scan_id: string | null;
}

export interface Scan {
  id: string;
  company_id: string;
  status: ScanStatus;
  reused: boolean;
  monitoring_categories: string[];
}

export interface ScanWithProgress extends Scan {
  progress: Record<string, string>;
  company_name: string | null;
  company_domain: string | null;
}

export interface ScanList {
  items: Scan[];
  next_cursor: string | null;
}

export interface Product {
  name: string;
  description?: string | null;
}

export interface Competitor {
  name: string;
  domain?: string | null;
  aliases: string[];
}

export interface ProfileIssue {
  field: string;
  value: string;
  reason: string;
}

export interface CompanyProfile {
  version: number;
  source: "ai_generated" | "user_edited" | "ai_verified";
  industry: string | null;
  description: string | null;
  aliases: string[];
  keywords: string[];
  products: Product[];
  competitors: Competitor[];
  confidence: number | null;
  warnings: string[];
  issues: ProfileIssue[];
}

export interface PatchProfileRequest {
  industry?: string;
  description?: string;
  aliases?: string[];
  products?: Product[];
  competitors?: Competitor[];
}

export interface DashboardSummary {
  ai_visibility: number;
  recommendation_rate: number;
  recommendation_rate_when_mentioned: number;
  share_of_voice: number;
  net_sentiment: number;
  responses_total: number;
  responses_evaluated: number;
}

export interface LeaderboardEntry {
  entity_id: string;
  name: string;
  is_target: boolean;
  mentions: number;
  positive: number;
  neutral: number;
  negative: number;
  avg_rank: number | null;
  rank_count: number;
}

export interface DiscoveredCompetitor {
  name: string;
  mentions: number;
}

export interface CategoryPerformance {
  category: string;
  visibility: number;
  n: number;
}

export interface ProviderComparison {
  provider: string;
  visibility: number;
  success_rate: number;
}

export type RankDistribution = Record<"1" | "2" | "3" | "4" | "5plus", number>;

export interface TopSource {
  domain: string;
  responses: number;
}

export interface DashboardMetrics {
  status: ScanStatus;
  status_detail: string | null;
  brand_only: boolean;
  summary: DashboardSummary;
  leaderboard: LeaderboardEntry[];
  discovered: DiscoveredCompetitor[];
  by_category: CategoryPerformance[];
  by_provider: ProviderComparison[];
  rank_distribution: RankDistribution;
  top_sources: TopSource[];
}

export interface PromptProviderSummary {
  status: string;
  target_mentioned: boolean | null;
  sentiment: string | null;
  recommended: boolean | null;
  rank_position: number | null;
}

export interface PromptListItem {
  id: string;
  text: string;
  category: string;
  target: string | null;
  providers: Record<string, PromptProviderSummary>;
}

export interface PromptList {
  items: PromptListItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface PromptResponseEvaluation {
  sentiment: string | null;
  target_mentioned: boolean;
  recommended: boolean;
  rank_position: number | null;
  mentioned_companies: string[];
  confidence: number | null;
  reasoning: string | null;
}

export interface PromptResponseDetail {
  provider: string;
  model: string;
  status: string;
  raw_response: string | null;
  citations: Array<Record<string, unknown>>;
  evaluation: PromptResponseEvaluation | null;
}

export interface PromptDetail {
  id: string;
  text: string;
  category: string;
  target: string | null;
  responses: PromptResponseDetail[];
}

export interface SourcesResponse {
  sources: TopSource[];
}
