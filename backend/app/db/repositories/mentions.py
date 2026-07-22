from app.db.models import Mention
from app.db.repositories.base import Repository


class MentionRepository(Repository[Mention]):
    model = Mention
