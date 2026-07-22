import type { ScanStatus } from "./types";

/** §6.1's status -> page map. Shared by every route so a reload at any
 * lifecycle stage lands on the right page (finalized end-to-end in Phase 20,
 * but the mapping itself only needs to be written once). */
export function statusToPath(id: string, status: ScanStatus): string {
  switch (status) {
    case "awaiting_verification":
    case "verifying":
      return `/scans/${id}/verify`;
    case "scope_pending":
      return `/scans/${id}/scope`;
    case "completed":
    case "completed_with_gaps":
      return `/scans/${id}/dashboard`;
    case "cancelled":
      return "/";
    default:
      return `/scans/${id}/progress`;
  }
}

/** Dashboard and Prompt Explorer are both only meaningful once a scan has
 * settled -- gate them on the same terminal statuses. */
export function isTerminalStatus(status: ScanStatus): boolean {
  return status === 'completed' || status === 'completed_with_gaps';
}
