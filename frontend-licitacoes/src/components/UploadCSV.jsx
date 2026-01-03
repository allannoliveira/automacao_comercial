import Papa from "papaparse"

export default function UploadCSV({ onLoad }) {
  function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (result) => {
        onLoad(result.data)
      }
    })
  }

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border">
      <label className="block text-sm font-medium mb-2">
        Importar CSV de licitações
      </label>

      <input
        type="file"
        accept=".csv"
        onChange={handleFile}
        className="block w-full text-sm file:mr-4 file:py-2 file:px-4
                   file:rounded-lg file:border-0
                   file:bg-blue-600 file:text-white
                   hover:file:bg-blue-700 cursor-pointer"
      />
    </div>
  )
}
