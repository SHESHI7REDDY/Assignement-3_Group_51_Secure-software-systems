from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = "sqlite:///./data/ballots.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


class StoredBallot(Base):
    __tablename__ = "ballots"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String, nullable=False)
    encrypted_ballot = Column(Text, nullable=False)


def initialise_database():
    Base.metadata.create_all(bind=engine)


def save_ballot(election_id: str, encrypted_ballot: str) -> int:
    db = SessionLocal()

    try:
        ballot = StoredBallot(
            election_id=election_id,
            encrypted_ballot=encrypted_ballot
        )

        db.add(ballot)
        db.commit()
        db.refresh(ballot)

        return ballot.id

    finally:
        db.close()
