from app.db.models import ScanEntity
from app.db.repositories.base import Repository


class ScanEntityRepository(Repository[ScanEntity]):
    model = ScanEntity
