"""PlanCategoryMultiplier ORM Model — Issue #74 方案 × 用量類別倍率"""

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class PlanCategoryMultiplierModel(Base):
    __tablename__ = "plan_category_multipliers"

    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plans.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usage_category: Mapped[str] = mapped_column(String(20), primary_key=True)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
