# Codebase Audit Findings

## Fixed in this pass

1. **Frontend build blocker:** missing `@/lib/utils` module used by setup components.
   - Added `frontend/lib/utils.ts` with a shared `cn()` helper.
2. **Polling lifecycle issue in campaign dashboard:** polling effect depended on mutable `data` state, causing interval recreation on every refresh and unnecessary re-renders.
   - Reworked to use a stable dependency list and `useRef` for completed-item tracking.
3. **Type safety issue for API contract:** dashboard `platform` field can be nullable from backend but frontend treated it as non-null.
   - Updated type and display fallback (`N/A`).
4. **Unused prop warning:** removed unused `targetBrand` prop from competitor leaderboard.
5. **Next.js image best-practice warning:** replaced `<img>` with `<Image>` and configured allowed remote host (`logo.clearbit.com`).
6. **Prompt/response format mismatch in backend LLM services:** prompts requested arrays while API requested JSON object response format.
   - Updated prompts/parsers to consistently use object payloads.
7. **Broad exception handling:** narrowed bare `except` in URL domain extraction to `ValueError`.

## Remaining risks / recommended follow-ups

1. **Frontend production build requires network access for Google Fonts.**
   - In restricted CI environments, `next build` fails fetching Geist fonts.
   - Recommendation: self-host fonts or add a local/system-font fallback path.
2. **API CORS is fully open (`allow_origins=["*"]`).**
   - Recommendation: restrict to trusted frontend origins in production.
3. **Synchronous LLM calls inside `async` functions (backend).**
   - `litellm.completion()` is called directly in async code, which can block the event loop under load.
   - Recommendation: switch to async client method (if available) or offload sync calls via thread executor.
4. **Error handling and observability.**
   - Several paths use `print()` and broad exception catches.
   - Recommendation: use structured logging and surface actionable HTTP errors where appropriate.
5. **Campaign prompt generation fallback is minimal (10 duplicate prompts).**
   - Recommendation: generate deterministic diversified fallback prompts to avoid low-quality campaigns.
