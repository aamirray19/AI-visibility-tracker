from app.db.models import JobRun
from app.db.repositories.base import Repository


class JobRunRepository(Repository[JobRun]):
    model = JobRun
