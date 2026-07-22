import uuid

from sqlalchemy import select

from app.db.models import Evaluation
from app.db.repositories.base import Repository


class EvaluationRepository(Repository[Evaluation]):
    model = Evaluation

    async def get_by_response(self, response_id: uuid.UUID) -> Evaluation | None:
        stmt = select(Evaluation).where(Evaluation.response_id == response_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
