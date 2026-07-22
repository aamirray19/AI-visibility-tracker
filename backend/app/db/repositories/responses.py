import uuid

from sqlalchemy import select

from app.db.models import AIResponse
from app.db.repositories.base import Repository


class AIResponseRepository(Repository[AIResponse]):
    model = AIResponse

    async def upsert(self, *, scan_id: uuid.UUID, prompt_id: uuid.UUID, provider: str, **fields) -> AIResponse:
        """§7.7: upsert on (prompt_id, provider) -- idempotent under retries."""
        stmt = select(AIResponse).where(AIResponse.prompt_id == prompt_id, AIResponse.provider == provider)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.attempts = (existing.attempts or 1) + 1
            await self.session.flush()
            return existing
        return await self.create(scan_id=scan_id, prompt_id=prompt_id, provider=provider, **fields)
