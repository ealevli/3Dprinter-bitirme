import { useState, useEffect, useRef } from "react";
import axios from "axios";
import PartUploader from "../components/PartUploader";

export default function PartsLibrary() {
  const [parts, setParts] = useState([]);
  const [showUploader, setShowUploader] = useState(false);
  const [retrainStatus, setRetrainStatus] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => {
    fetchParts();
    return () => clearInterval(pollRef.current);
  }, []);

  async function fetchParts() {
    const res = await axios.get("/parts").catch(() => null);
    if (res) setParts(res.data.parts);
  }

  async function handleDelete(id) {
    await axios.delete(`/parts/${id}`).catch(() => {});
    fetchParts();
  }

  async function handleRetrain() {
    setRetrainStatus("Eğitim başlatılıyor…");
    await axios.post("/parts/retrain").catch(() => {});
    pollRef.current = setInterval(async () => {
      const res = await axios.get("/parts/retrain/status").catch(() => null);
      if (!res) return;
      const s = res.data;
      if (s.status === "done") {
        setRetrainStatus("Eğitim tamamlandı.");
        clearInterval(pollRef.current);
      } else if (s.status === "error") {
        setRetrainStatus(`Hata: ${s.error}`);
        clearInterval(pollRef.current);
      } else {
        setRetrainStatus(`Eğitiliyor… %${s.progress}`);
      }
    }, 1500);
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Parça Kütüphanesi</h1>
        <div className="flex gap-2">
          <button
            onClick={handleRetrain}
            className="px-3 py-1.5 text-sm rounded bg-purple-600 hover:bg-purple-500"
          >
            Modeli Eğit
          </button>
          <button
            onClick={() => setShowUploader(true)}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 hover:bg-blue-500"
          >
            + Yeni Parça
          </button>
        </div>
      </div>

      {retrainStatus && (
        <div className="bg-slate-800 rounded p-2 text-sm text-slate-300">
          {retrainStatus}
        </div>
      )}

      {showUploader && (
        <PartUploader
          onClose={() => setShowUploader(false)}
          onSaved={fetchParts}
        />
      )}

      {parts.length === 0 ? (
        <p className="text-slate-500 text-sm">
          Henüz parça eklenmedi. "+ Yeni Parça" ile ekleyin.
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {parts.map((p) => (
            <div key={p.id} className="bg-slate-800 rounded-lg p-3 flex flex-col gap-2">
              {p.image_path ? (
                <img
                  src={`/parts/${p.id}/image`}
                  alt={p.name}
                  className="w-full h-28 object-cover rounded"
                />
              ) : (
                <div className="w-full h-28 bg-slate-700 rounded flex items-center justify-center text-slate-500 text-xs">
                  Fotoğraf yok
                </div>
              )}
              <p className="font-medium text-sm truncate">{p.name}</p>
              <p className="text-xs text-slate-400">
                Aralık: {p.default_params?.line_spacing ?? 1.0} mm &nbsp;|&nbsp;
                Z: {p.default_params?.z_offset ?? 0.3} mm
              </p>
              <button
                onClick={() => handleDelete(p.id)}
                className="mt-auto text-xs text-red-400 hover:text-red-300 text-left"
              >
                Sil
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
