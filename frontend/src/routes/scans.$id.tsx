import { createFileRoute, Outlet } from "@tanstack/react-router";

// Layout route for the /scans/:id/... tree (§6.1). Child pages (verify,
// scope, progress, dashboard, prompts) are added one per phase in
// Phases 16-20; this just establishes the segment so `$id` is available to
// every child route's loader/component via useParams.
export const Route = createFileRoute("/scans/$id")({
  component: () => <Outlet />,
});
