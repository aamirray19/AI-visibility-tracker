import uuid

from sqlalchemy import select

from app.db.models import CompanyProfile
from app.db.repositories.base import Repository


class CompanyProfileRepository(Repository[CompanyProfile]):
    model = CompanyProfile

    async def get_latest(self, scan_id: uuid.UUID) -> CompanyProfile | None:
        stmt = (
            select(CompanyProfile)
            .where(CompanyProfile.scan_id == scan_id)
            .order_by(CompanyProfile.version.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
