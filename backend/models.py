from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Boletim(Base):
    __tablename__ = "boletins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    boletim_id = Column(Integer)
    bidding_id = Column(Integer)
    edital = Column(String(50))
    data_abertura = Column(DateTime)
    prazo = Column(String(50))
    data_coleta = Column(DateTime)
    valor_estimado = Column(Numeric(15, 2))
    cidade = Column(String(100))
    estado = Column(String(10))
    situacao = Column(String(50))
    descricao = Column(Text)
