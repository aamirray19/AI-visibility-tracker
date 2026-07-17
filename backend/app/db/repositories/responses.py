from app.db.models import AIResponse
from app.db.repositories.base import Repository


class AIResponseRepository(Repository[AIResponse]):
    model = AIResponse
