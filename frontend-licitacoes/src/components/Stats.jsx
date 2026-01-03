export default function Stats({ licitacoes }) {
  const total = licitacoes.length;

  const valorTotal = licitacoes.reduce((acc, l) => {
    const valor = l.valor_estimado
      ?.replace("R$", "")
      ?.replace(/\./g, "")
      ?.replace(",", ".");
    return acc + (parseFloat(valor) || 0);
  }, 0);

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-neutral-800 rounded-xl p-5">
        <p className="text-sm text-gray-400">Licitações encontradas</p>
        <p className="text-3xl font-semibold mt-2">{total}</p>
      </div>

      <div className="bg-neutral-800 rounded-xl p-5">
        <p className="text-sm text-gray-400">Valor estimado total</p>
        <p className="text-2xl font-semibold mt-2">
          R$ {valorTotal.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
        </p>
      </div>
    </section>
  );
}
