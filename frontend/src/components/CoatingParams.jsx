export default function CoatingParams({ params, onChange }) {
  function set(key, value) {
    onChange({ ...params, [key]: value });
  }

  const field = (label, key, type = "number", extra = {}) => (
    <div>
      <label className="text-xs text-slate-400 block mb-1">{label}</label>
      <input
        type={type}
        value={params[key]}
        onChange={(e) =>
          set(key, type === "number" ? parseFloat(e.target.value) : e.target.value)
        }
        className="w-full bg-slate-700 rounded px-2 py-1 text-sm"
        {...extra}
      />
    </div>
  );

  return (
    <div className="bg-slate-800 rounded-lg p-4 space-y-3">
      <h3 className="font-semibold text-sm">Kaplama Parametreleri</h3>

      {field("Çizgi aralığı (mm)", "line_spacing", "number", { step: 0.1, min: 0.1 })}
      {field("Z-offset (mm)", "z_offset", "number", { step: 0.1, min: 0 })}
      {field("Feed rate (mm/min)", "feed_rate", "number", { step: 50, min: 50 })}
      {field("Travel rate (mm/min)", "travel_rate", "number", { step: 50, min: 100 })}
      {field("Bant kalınlığı (mm)", "band_thickness", "number", { step: 0.1, min: 0 })}

      <div>
        <label className="text-xs text-slate-400 block mb-1">Pattern</label>
        <select
          value={params.pattern_type}
          onChange={(e) => set("pattern_type", e.target.value)}
          className="w-full bg-slate-700 rounded px-2 py-1 text-sm"
        >
          <option value="zigzag">Zigzag</option>
          <option value="parallel">Paralel</option>
          <option value="spiral">Spiral</option>
        </select>
      </div>
    </div>
  );
}
