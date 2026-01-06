import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Calendar,
  MapPin,
  DollarSign,
  Clock,
  FileText,
} from "lucide-react";

export default function LicitacaoCard({ data }) {
  const [expanded, setExpanded] = useState(false);

  const getStatusStyle = (situacao = "") => {
    const s = situacao.toLowerCase().trim();

    if (s.includes("urgente") || s.includes("consulta") || s.includes("erro"))
      return { bg: "bg-orange-600", label: "Urgente" };
    if (s.includes("normal")) return { bg: "bg-gray-600", label: "Normal" };
    if (s.includes("aberta")) return { bg: "bg-blue-600", label: "Aberta" };
    if (s.includes("andamento")) return { bg: "bg-cyan-600", label: "Em andamento" };
    if (s.includes("vencida")) return { bg: "bg-green-600", label: "Vencida" };

    return { bg: "bg-gray-600", label: situacao || "Normal" };
  };

  const status = getStatusStyle(data.situacao);

  return (
    <div
      className="
        bg-neutral-800 rounded-xl border border-neutral-700 
        shadow-lg shadow-black/40 hover:shadow-2xl hover:shadow-black/50
        transition-all duration-300 flex flex-col overflow-hidden
        w-full h-auto lg:h-[480px]
      "
    >
      {/* Badge */}
      <div className="h-12 sm:h-14 relative flex-shrink-0">
        <div className="absolute top-3 right-3 sm:top-4 sm:right-4 z-10">
          <span
            className={`
              px-3 sm:px-4 py-1 sm:py-1.5
              text-[10px] sm:text-xs font-bold
              rounded-full text-white uppercase tracking-wider
              ${status.bg} shadow-md shadow-black/40
            `}
          >
            {status.label}
          </span>
        </div>
      </div>

      {/* Conteúdo */}
      <div className="flex-grow flex flex-col
        pl-4 pr-4 sm:pl-6 sm:pr-6 lg:pr-8
        pt-2 pb-4 sm:pb-5
      ">
        <div className="text-[11px] sm:text-xs text-neutral-400 mb-2 sm:mb-3 px-1 pr-4">
          ID Licitação #{data.bidding_id || "N/A"}
        </div>

        <h3
          className="
            font-semibold text-white
            text-sm sm:text-base leading-tight
            mb-4 sm:mb-5
            line-clamp-2 sm:line-clamp-3
            px-1 pr-8 sm:pr-10
          "
        >
          {data.edital || "Edital não informado"}
        </h3>

        <div className="space-y-3 sm:space-y-4 text-sm text-neutral-300 flex-grow px-1 pr-4 sm:pr-6">
          <div className="flex items-start gap-3">
            <MapPin className="w-4 h-4 sm:w-5 sm:h-5 text-neutral-400 mt-0.5" />
            <span className="text-xs sm:text-sm line-clamp-1">
              {data.cidade || "—"} {data.estado ? `- ${data.estado}` : ""}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Calendar className="w-4 h-4 sm:w-5 sm:h-5 text-neutral-400" />
            <span className="text-xs sm:text-sm line-clamp-1">
              Abertura: {data.data_abertura || "Não informada"}
            </span>
          </div>

          {data.prazo && (
            <div className="flex items-center gap-3">
              <Clock className="w-4 h-4 sm:w-5 sm:h-5 text-neutral-400" />
              <span className="text-xs sm:text-sm line-clamp-1">
                Prazo: {data.prazo}
              </span>
            </div>
          )}

          <div className="mt-auto pt-4 sm:pt-6 flex items-center gap-3 pr-4 sm:pr-6">
            <DollarSign className="w-5 h-5 sm:w-6 sm:h-6 text-emerald-400" />
            <span className="text-xl sm:text-2xl font-bold text-emerald-400 truncate">
              {data.valor_estimado || "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Botão */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="
          w-full px-4 sm:px-6 py-3 sm:py-4
          flex items-center justify-between
          text-xs sm:text-sm text-neutral-400 hover:text-white
          bg-neutral-900/70 hover:bg-neutral-800
          border-t border-neutral-700 transition-colors
        "
      >
        <div className="flex items-center gap-2 sm:gap-3">
          <FileText className="w-4 h-4 sm:w-5 sm:h-5" />
          <span>{expanded ? "Ocultar descrição" : "Ver descrição completa"}</span>
        </div>

        <span
          className={`
            transition-transform duration-300
            ${expanded ? "rotate-180" : ""}
          `}
        >
          <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5" />
        </span>
      </button>

      {/* 🔥 EXPAND / COLLAPSE ANIMADO */}
      <div
        className={`
          grid transition-all duration-300 ease-in-out
          ${expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}
        `}
      >
        <div className="overflow-hidden">
          <div className="pl-4 pr-4 sm:pl-6 sm:pr-6 lg:pr-8 pb-5 pt-4 border-t border-neutral-700 bg-neutral-900/60">
            <div className="text-sm text-neutral-300 leading-relaxed px-1 pr-4 sm:pr-6">
              {data.descricao || "Sem descrição disponível."}
            </div>

            {data.boletim_id && (
              <div className="mt-4 text-xs text-neutral-500 pt-3 border-t border-neutral-800 px-1 pr-4 sm:pr-6">
                Boletim ID: {data.boletim_id}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
