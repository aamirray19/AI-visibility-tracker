from app.db.models import ScanMetrics
from app.db.repositories.base import Repository


class ScanMetricsRepository(Repository[ScanMetrics]):
    model = ScanMetrics
