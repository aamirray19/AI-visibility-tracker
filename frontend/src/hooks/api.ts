import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  CompanyProfile,
  DashboardMetrics,
  MonitoringCategory,
  PatchProfileRequest,
  PromptDetail,
  PromptList,
  ResolveCompanyResponse,
  Scan,
  ScanWithProgress,
} from "@/lib/types";

export function useResolveCompany() {
  return useMutation({
    mutationFn: (body: { name: string; website: string }) =>
      api.post<ResolveCompanyResponse>("/api/v1/companies/resolve", body),
  });
}

export function useCreateScan() {
  return useMutation({
    mutationFn: ({ name, website, force }: { name: string; website: string; force?: boolean }) =>
      api.post<Scan>(`/api/v1/scans${force ? "?force=true" : ""}`, { name, website }),
  });
}

export function useScan(
  scanId: string | undefined,
  options: { refetchInterval?: UseQueryOptions<ScanWithProgress>["refetchInterval"] } = {},
) {
  return useQuery({
    queryKey: ["scan", scanId],
    queryFn: () => api.get<ScanWithProgress>(`/api/v1/scans/${scanId}`),
    enabled: !!scanId,
    refetchInterval: options.refetchInterval,
  });
}

export function useProfile(scanId: string | undefined) {
  return useQuery({
    queryKey: ["profile", scanId],
    queryFn: () => api.get<CompanyProfile>(`/api/v1/scans/${scanId}/profile`),
    enabled: !!scanId,
  });
}

export function usePatchProfile(scanId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PatchProfileRequest) => api.patch<CompanyProfile>(`/api/v1/scans/${scanId}/profile`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profile", scanId] }),
  });
}

export function useConfirmProfile(scanId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CompanyProfile>(`/api/v1/scans/${scanId}/profile/confirm`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", scanId] });
      queryClient.invalidateQueries({ queryKey: ["scan", scanId] });
    },
  });
}

export function useScope(scanId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (categories?: MonitoringCategory[]) =>
      api.put<Scan>(`/api/v1/scans/${scanId}/scope`, { categories }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan", scanId] }),
  });
}

export function useLaunch(scanId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Scan>(`/api/v1/scans/${scanId}/launch`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan", scanId] }),
  });
}

export function useCancelScan(scanId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>(`/api/v1/scans/${scanId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan", scanId] }),
  });
}

export function useDashboard(scanId: string | undefined) {
  return useQuery({
    queryKey: ["dashboard", scanId],
    queryFn: () => api.get<DashboardMetrics>(`/api/v1/scans/${scanId}/dashboard`),
    enabled: !!scanId,
  });
}

export interface PromptFilters {
  category?: string;
  provider?: string;
  sentiment?: string;
  mentioned?: boolean;
  offset?: number;
  limit?: number;
}

export function usePrompts(scanId: string | undefined, filters: PromptFilters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const qs = params.toString();
  return useQuery({
    queryKey: ["prompts", scanId, filters],
    queryFn: () => api.get<PromptList>(`/api/v1/scans/${scanId}/prompts${qs ? `?${qs}` : ""}`),
    enabled: !!scanId,
  });
}

export function usePromptDetail(scanId: string | undefined, promptId: string | null) {
  return useQuery({
    queryKey: ["promptDetail", scanId, promptId],
    queryFn: () => api.get<PromptDetail>(`/api/v1/scans/${scanId}/prompts/${promptId}`),
    enabled: !!scanId && !!promptId,
  });
}
