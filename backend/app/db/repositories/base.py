import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    """Thin CRUD wrapper over one table. Scan-scoped queries live here so a
    future `user_id` filter is one `where` clause per repository, not a rewrite."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **fields) -> ModelT:
        obj = self.model(**fields)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def list(self, **filters) -> list[ModelT]:
        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()
