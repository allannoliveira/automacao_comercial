import { useEffect, useState } from "react";
import Papa from "papaparse";
import Header from "./components/Header";
import Stats from "./components/Stats";
import LicitacoesBoard from "./components/LicitacoesBoard";


function App() {
  const [licitacoes, setLicitacoes] = useState([]);

  useEffect(() => {
    fetch("/licitacoes_filtradas.csv")
      .then((res) => res.text())
      .then((csv) => {
        Papa.parse(csv, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            // Filtra linhas vazias que o PapaParse às vezes deixa
            const dados = results.data.filter(item => item.bidding_id);
            setLicitacoes(dados);
          },
        });
      })
      .catch(err => console.error("Erro ao carregar CSV:", err));
  }, []);

  return (
    <div className="min-h-screen bg-neutral-900 text-white">
      <Header />
      <main className="max-w-screen-2xl mx-auto px-8 py-6">
        <Stats licitacoes={licitacoes} />
        <LicitacoesBoard licitacoes={licitacoes} />
      </main>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #262626; border-radius: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #404040; border-radius: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #525252; }
      `}</style>
    </div>
  );
}

export default App;