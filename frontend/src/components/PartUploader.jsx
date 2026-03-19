import { useState, useRef } from "react";
import axios from "axios";

export default function PartUploader({ onClose, onSaved }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [params, setParams] = useState({
    line_spacing: 1.0,
    z_offset: 0.3,
    feed_rate: 600,
    pattern_type: "zigzag",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  function handleFileChange(f) {
    if (!f) return;
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreview(url);
  }

  async function handleSave() {
    if (!name.trim()) {
      setError("Parça adı gerekli.");
      return;
    }
    setSaving(true);
    setError("");
    const formData = new FormData();
    formData.append("name", name.trim());
    formData.append("default_params", JSON.stringify(params));
    if (file) formData.append("image", file);

    try {
      await axios.post("/parts", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onSaved?.();
      onClose?.();
    } catch (err) {
      setError(err.response?.data?.detail ?? "Kayıt başarısız.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-lg">Yeni Parça Ekle</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">×</button>
        </div>

        {/* Drag-drop image */}
        <div
          className="border-2 border-dashed border-slate-600 rounded-lg h-36 flex items-center justify-center cursor-pointer hover:border-blue-500 transition-colors"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFileChange(e.dataTransfer.files[0]);
          }}
        >
          {preview ? (
            <img src={preview} alt="preview" className="h-full object-contain rounded" />
          ) : (
            <p className="text-slate-500 text-sm">Fotoğraf sürükle veya tıkla</p>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFileChange(e.target.files[0])}
        />

        <div>
          <label className="text-xs text-slate-400 block mb-1">Parça Adı</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-slate-700 rounded px-3 py-2 text-sm"
            placeholder="ör: kare_plaka"
          />
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ["Çizgi aralığı (mm)", "line_spacing", 0.1],
            ["Z-offset (mm)", "z_offset", 0.1],
            ["Feed rate", "feed_rate", 50],
          ].map(([label, key, step]) => (
            <div key={key}>
              <label className="text-xs text-slate-400 block mb-1">{label}</label>
              <input
                type="number"
                step={step}
                value={params[key]}
                onChange={(e) =>
                  setParams({ ...params, [key]: parseFloat(e.target.value) })
                }
                className="w-full bg-slate-700 rounded px-2 py-1"
              />
            </div>
          ))}
          <div>
            <label className="text-xs text-slate-400 block mb-1">Pattern</label>
            <select
              value={params.pattern_type}
              onChange={(e) => setParams({ ...params, pattern_type: e.target.value })}
              className="w-full bg-slate-700 rounded px-2 py-1"
            >
              <option value="zigzag">Zigzag</option>
              <option value="parallel">Paralel</option>
              <option value="spiral">Spiral</option>
            </select>
          </div>
        </div>

        {error && <p className="text-red-400 text-xs">{error}</p>}

        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 py-2 rounded bg-slate-700 hover:bg-slate-600 text-sm">
            İptal
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm font-medium"
          >
            {saving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}
