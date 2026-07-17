from app.db.models import Company
from app.db.repositories.base import Repository


class CompanyRepository(Repository[Company]):
    model = Company
