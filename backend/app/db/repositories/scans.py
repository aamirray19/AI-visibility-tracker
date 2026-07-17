from app.db.models import Scan
from app.db.repositories.base import Repository


class ScanRepository(Repository[Scan]):
    model = Scan
