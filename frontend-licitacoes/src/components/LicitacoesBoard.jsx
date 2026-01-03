import LicitacaoCard from "./LicitacaoCard";

export default function LicitacoesBoard({ licitacoes }) {
  if (!licitacoes?.length) {
    return (
      <div className="text-center py-12 text-neutral-400">
        Nenhuma licitação encontrada.
      </div>
    );
  }

  return (
    <section className="mt-8 pb-12">
      <div className="flex items-center justify-between mb-6 max-w-[1300px] mx-auto px-6 sm:px-8 lg:px-12">
        <h2 className="text-2xl font-bold">Licitações</h2>
        <span className="text-sm text-neutral-400">{licitacoes.length} itens</span>
      </div>
      
      {/* Container centralizado com 3 colunas */}
      <div className="flex justify-center w-full px-6 sm:px-8 lg:px-12">
        <div 
          className="
            grid 
            grid-cols-1 
            md:grid-cols-2 
            lg:grid-cols-3 
            gap-6 lg:gap-8
            w-full
            max-w-[1300px]
          "
        >
          {licitacoes.map((item, index) => (
            <LicitacaoCard 
              key={item.bidding_id || index} 
              data={item} 
            />
          ))}
        </div>
      </div>
    </section>
  );
}