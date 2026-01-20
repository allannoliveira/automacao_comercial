let licitacoes = [];
let receita = 0;

// SIMULA API (troque por fetch real)
fetch("http://127.0.0.1:5000/boletins")
  .then(res => res.json())
  .then(data => {
    licitacoes = data;
    renderizar(licitacoes);
  });

function aplicarFiltros() {
  const cidade = filtroCidade.value.toLowerCase();
  const estado = filtroEstado.value.toLowerCase();
  const valorMin = parseFloat(filtroValor.value || 0);

  const filtradas = licitacoes.filter(l => {
    const valor = parseValor(l.valor_estimado);
    return (
      (!cidade || l.cidade.toLowerCase().includes(cidade)) &&
      (!estado || l.estado.toLowerCase().includes(estado)) &&
      valor >= valorMin
    );
  });

  renderizar(filtradas);
}

function renderizar(lista) {
  board.innerHTML = "";
  receita = 0;

  lista.forEach(l => {
    const col = document.createElement("div");
    col.className = "col-md-4 col-lg-3";

    const cardId = `c${l.boletim_id}`;

    col.innerHTML = `
      <div class="card-licitacao">
        <div data-bs-toggle="collapse" data-bs-target="#${cardId}">
          <small>ID</small>
          <div class="fw-bold">${l.boletim_id}</div>

          <div class="text-secondary">${l.cidade} - ${l.estado}</div>

          <div class="mt-2 fw-semibold">${l.edital}</div>

          <div class="mt-2 fw-bold text-primary">${l.valor_estimado}</div>

          <span class="badge badge-situacao mt-2">
            ${l.situacao || "Não informado"}
          </span>
        </div>

        <div id="${cardId}" class="collapse mt-3">
          <hr/>
          <div><strong>Abertura:</strong> ${l.data_abertura}</div>
          <div class="descricao mt-2">${l.descricao}</div>

          <button
            class="btn btn-outline-primary btn-sm mt-3 w-100"
            onclick="participar(${parseValor(l.valor_estimado)})"
          >
            Participar
          </button>
        </div>
      </div>
    `;

    board.appendChild(col);
  });

  atualizarResumo(lista);
}

function participar(valor) {
  receita += valor * 0.1;
  atualizarReceita();
}

function atualizarResumo(lista) {
  totalLicitacoes.innerText = lista.length;

  const total = lista.reduce((acc, l) => acc + parseValor(l.valor_estimado), 0);
  valorTotal.innerText = formatar(total);
}

function atualizarReceita() {
  receitaEstimada.innerText = formatar(receita);
}

function parseValor(v) {
  return parseFloat(
    (v || "0").replace("R$", "").replace(/\./g, "").replace(",", ".")
  ) || 0;
}

function formatar(v) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
