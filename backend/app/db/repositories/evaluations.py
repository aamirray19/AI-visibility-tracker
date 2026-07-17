from app.db.models import Evaluation
from app.db.repositories.base import Repository


class EvaluationRepository(Repository[Evaluation]):
    model = Evaluation
