import { useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { statusToPath } from '@/lib/status';
import type { ScanStatus } from '@/lib/types';

/** §6.1/Phase 20: shared reload-guard for every lifecycle page -- redirects
 * to the right page (via `statusToPath`) the moment a fetched `status`
 * doesn't belong on the current one. `isAllowed` should be a stable
 * (module-scope) function/Set-backed predicate, not an inline arrow, so the
 * effect doesn't re-fire every render. */
export function useStatusGuard(id: string, status: ScanStatus | undefined, isAllowed: (status: ScanStatus) => boolean) {
  const navigate = useNavigate();
  useEffect(() => {
    if (status && !isAllowed(status)) {
      navigate({ to: statusToPath(id, status) });
    }
  }, [status, id, navigate, isAllowed]);
}
