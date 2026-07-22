"""Queue name constants (§8), split out from worker/settings.py so jobs.py
can reference them for its own enqueue calls without a circular import
(settings.py imports the job functions from jobs.py)."""

INTERACTIVE_QUEUE = "arq:interactive"
PIPELINE_QUEUE = "arq:pipeline"
