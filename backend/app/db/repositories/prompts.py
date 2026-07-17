from app.db.models import Prompt
from app.db.repositories.base import Repository


class PromptRepository(Repository[Prompt]):
    model = Prompt
