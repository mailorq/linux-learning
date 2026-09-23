from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class ProgressStoreError(Exception):
    pass


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("attempts >= solved and solved >= solved_without_hints"),
        CheckConstraint("hints_used >= 0 and progress_penalty >= 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    solved: Mapped[int] = mapped_column(Integer, nullable=False)
    solved_without_hints: Mapped[int] = mapped_column(Integer, nullable=False)
    hints_used: Mapped[int] = mapped_column(Integer, nullable=False)
    progress_penalty: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_errors: Mapped[list[TopicErrorRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class TopicErrorRecord(Base):
    __tablename__ = "topic_errors"
    __table_args__ = (CheckConstraint("count > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    session: Mapped[SessionRecord] = relationship(back_populates="topic_errors")


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    sessions: int
    attempts: int
    solved: int
    solved_without_hints: int
    hints_used: int
    progress_penalty: int
    topic_errors: tuple[tuple[str, int], ...]


class ProgressStore:
    def __init__(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            Base.metadata.create_all(engine)
            self._engine = engine
        except (OSError, SQLAlchemyError) as exc:
            raise ProgressStoreError("не удалось открыть хранилище прогресса") from exc

    def save_session(
        self,
        *,
        attempts: int,
        solved: int,
        solved_without_hints: int,
        hints_used: int,
        progress_penalty: int,
        topic_errors: Mapping[str, int],
    ) -> None:
        record = SessionRecord(
            attempts=attempts,
            solved=solved,
            solved_without_hints=solved_without_hints,
            hints_used=hints_used,
            progress_penalty=progress_penalty,
            topic_errors=[
                TopicErrorRecord(topic=topic, count=count)
                for topic, count in topic_errors.items()
                if count > 0
            ],
        )
        try:
            with Session(self._engine) as session, session.begin():
                session.add(record)
        except SQLAlchemyError as exc:
            raise ProgressStoreError("не удалось сохранить прогресс") from exc

    def load_summary(self) -> ProgressSummary:
        try:
            with Session(self._engine) as session:
                totals = session.execute(
                    select(
                        func.count(SessionRecord.id),
                        func.coalesce(func.sum(SessionRecord.attempts), 0),
                        func.coalesce(func.sum(SessionRecord.solved), 0),
                        func.coalesce(func.sum(SessionRecord.solved_without_hints), 0),
                        func.coalesce(func.sum(SessionRecord.hints_used), 0),
                        func.coalesce(func.sum(SessionRecord.progress_penalty), 0),
                    )
                ).one()
                topic_rows = session.execute(
                    select(
                        TopicErrorRecord.topic,
                        func.sum(TopicErrorRecord.count).label("failures"),
                    )
                    .group_by(TopicErrorRecord.topic)
                    .order_by(func.sum(TopicErrorRecord.count).desc(), TopicErrorRecord.topic)
                ).all()
        except SQLAlchemyError as exc:
            raise ProgressStoreError("не удалось прочитать прогресс") from exc

        return ProgressSummary(
            sessions=int(totals[0]),
            attempts=int(totals[1]),
            solved=int(totals[2]),
            solved_without_hints=int(totals[3]),
            hints_used=int(totals[4]),
            progress_penalty=int(totals[5]),
            topic_errors=tuple((topic, int(count)) for topic, count in topic_rows),
        )

    def close(self) -> None:
        self._engine.dispose()
