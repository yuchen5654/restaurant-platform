import uuid as _uuid

from sqlalchemy import Column, Date, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class BenchmarkStats(Base):
    __tablename__ = 'benchmark_stats'
    __table_args__ = (
        UniqueConstraint('metric', 'cohort', 'stat_date', name='uq_benchmark_metric_cohort_date'),
    )

    id        = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    metric    = Column(String(50), nullable=False)
    cohort    = Column(String(50), nullable=False)
    stat_date = Column(Date, nullable=False)
    p25       = Column(Numeric(10, 4), nullable=False)
    p50       = Column(Numeric(10, 4), nullable=False)
    p75       = Column(Numeric(10, 4), nullable=False)
    n         = Column(Integer, nullable=False)
