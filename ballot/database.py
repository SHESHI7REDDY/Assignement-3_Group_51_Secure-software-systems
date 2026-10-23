from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./ballots.db"

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


Base.metadata.create_all(bind=engine)