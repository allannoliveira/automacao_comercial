from flask import Flask, jsonify, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask_cors import CORS

from models import Base, Boletim

# ATENÇÃO AO NOME DO BANCO (acentuação)
DATABASE_URL = "mysql+pymysql://root:@localhost/licitacoes"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

app = Flask(__name__)
CORS(app)

@app.route("/boletins", methods=["GET"])
def listar_boletins():
    session = SessionLocal()

    boletins = session.query(Boletim).all()
    session.close()

    return jsonify([
        {
            "id": b.id,
            "boletim_id": b.boletim_id,
            "bidding_id": b.bidding_id,
            "edital": b.edital,
            "data_abertura": b.data_abertura.isoformat() if b.data_abertura else None,
            "prazo": b.prazo,
            "data_coleta": b.data_coleta.isoformat() if b.data_coleta else None,
            "valor_estimado": float(b.valor_estimado) if b.valor_estimado else None,
            "cidade": b.cidade,
            "estado": b.estado,
            "situacao": b.situacao,
            "descricao": b.descricao
        }
        for b in boletins
    ])

if __name__ == "__main__":
    app.run(debug=True)
