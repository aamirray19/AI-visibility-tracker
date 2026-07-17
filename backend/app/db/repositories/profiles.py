from app.db.models import CompanyProfile
from app.db.repositories.base import Repository


class CompanyProfileRepository(Repository[CompanyProfile]):
    model = CompanyProfile
