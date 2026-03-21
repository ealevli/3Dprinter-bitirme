import { useState } from "react";

// ── Parametre tanımları ────────────────────────────────────────────────────────
// Her parametre için: ne işe yarar, nasıl ayarlanır, önerilen aralık
const PARAM_INFO = {
  line_spacing: {
    label: "Çizgi Aralığı (mm)",
    unit: "mm",
    min: 0.2,
    max: 5,
    step: 0.1,
    color: "blue",
    short: "Kaplama çizgileri arasındaki mesafe",
    detail: [
      "Küçük değer (0.5–1 mm) → daha yoğun kaplama, daha uzun süre, çözelti daha çok harcar",
      "Büyük değer (2–4 mm) → seyrek kaplama, hızlı biter, aralıklı çizgi görünür",
      "Başlangıç için 1 mm önerilir — sonra sonuca göre ayarla",
    ],
    presets: [
      { label: "Yoğun", value: 0.5 },
      { label: "Normal", value: 1.0 },
      { label: "Seyrek", value: 2.0 },
    ],
  },
  z_offset: {
    label: "Z-Offset (mm)",
    unit: "mm",
    min: 0.1,
    max: 3,
    step: 0.05,
    color: "purple",
    short: "Nozzle ucu ile parça yüzeyi arasındaki boşluk",
    detail: [
      "BLTouch Z=0'ı tabla yüzeyine kalibre eder. Z-Offset, BUNUN ÜSTÜNDEKİ ek boşluktur.",
      "0.3–0.5 mm → ideal: çözelti damlacık yapmadan yüzeye değer",
      "Çok az (< 0.2 mm) → nozzle yüzeye sürtebilir",
      "Çok fazla (> 1 mm) → çözelti akar, düzgün yayılmaz",
      "Gerçek kaplama Z = Bant Kalınlığı + Z-Offset",
    ],
    presets: [
      { label: "Yakın", value: 0.2 },
      { label: "Normal", value: 0.3 },
      { label: "Uzak", value: 0.5 },
    ],
  },
  feed_rate: {
    label: "Feed Rate (mm/dak)",
    unit: "mm/dak",
    min: 100,
    max: 3000,
    step: 50,
    color: "green",
    short: "Kaplama yaparken yazıcının hareket hızı",
    detail: [
      "Yavaş (300–500) → çözelti daha uzun süre akar, daha kalın tabaka",
      "Normal (600–800) → iyi denge, önerilen başlangıç noktası",
      "Hızlı (1000+) → ince/hafif kaplama, çözelti yetişemeyebilir",
      "Pompanın debisiyle uyumlu olmalı — pompa yavaşsa feed rate de yavaş olsun",
    ],
    presets: [
      { label: "Yavaş", value: 400 },
      { label: "Normal", value: 600 },
      { label: "Hızlı", value: 1000 },
    ],
  },
  travel_rate: {
    label: "Travel Rate (mm/dak)",
    unit: "mm/dak",
    min: 500,
    max: 6000,
    step: 100,
    color: "slate",
    short: "Boş harekette (kaplama yapmadan) yazıcının hızı",
    detail: [
      "Kaplama yapmadığında nozzle hızlı gider, bu süreyi kısaltır",
      "1500–3000 aralığı güvenli ve hızlı",
      "Çok yüksek değer (> 4000) yazıcının kaymasına neden olabilir",
      "Genellikle değiştirmene gerek yok — 1500 bırak",
    ],
    presets: [
      { label: "Normal", value: 1500 },
      { label: "Hızlı", value: 3000 },
    ],
  },
  band_thickness: {
    label: "Bant Kalınlığı (mm)",
    unit: "mm",
    min: 0,
    max: 5,
    step: 0.1,
    color: "amber",
    short: "Parçanın altındaki çift taraflı bandın kalınlığı — CETVEL İLE ÖLÇÜN",
    detail: [
      "BLTouch Z=0'ı tabla yüzeyi olarak ayarlar. Ama parçanız bant üzerinde yüksekte!",
      "Bant kalınlığı = parçanın tabla yüzeyinden ne kadar yukarıda olduğu",
      "Cetvelle ölçün: kargo bandı ≈ 0.5–1 mm, köpük bant ≈ 2–3 mm",
      "Yanlış değer → nozzle parçaya çarpar (çok az) veya hiç değmez (çok fazla)",
      "Gerçek kaplama Z = Bant Kalınlığı + Z-Offset",
    ],
    presets: [
      { label: "İnce", value: 0.5 },
      { label: "Normal", value: 1.0 },
      { label: "Kalın", value: 2.0 },
    ],
  },
};

// ── Tooltip bileşeni ─────────────────────────────────────────────────────────
function InfoTooltip({ info }) {
  const [open, setOpen] = useState(false);
  const colors = {
    blue: "border-blue-500 bg-blue-950",
    purple: "border-purple-500 bg-purple-950",
    green: "border-green-500 bg-green-950",
    slate: "border-slate-500 bg-slate-900",
    amber: "border-amber-500 bg-amber-950",
  };

  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setOpen((p) => !p)}
        className="w-4 h-4 rounded-full bg-slate-600 text-slate-300 text-xs flex items-center justify-center hover:bg-slate-500 leading-none"
        tabIndex={-1}
      >
        ?
      </button>
      {open && (
        <div
          className={`absolute right-0 bottom-6 z-50 w-72 border rounded-lg p-3 text-xs shadow-xl ${colors[info.color] ?? colors.slate}`}
        >
          <p className="font-semibold text-white mb-2">{info.short}</p>
          <ul className="space-y-1 text-slate-300">
            {info.detail.map((d, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="text-slate-500 shrink-0">•</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Ana bileşen ──────────────────────────────────────────────────────────────
export default function CoatingParams({ params, onChange }) {
  function set(key, value) {
    onChange({ ...params, [key]: value });
  }

  return (
    <div className="bg-slate-800 rounded-lg p-4 space-y-4">
      <h3 className="font-semibold text-sm">Kaplama Parametreleri</h3>

      {/* Sayısal parametreler */}
      {Object.entries(PARAM_INFO).map(([key, info]) => (
        <div key={key} className="space-y-1.5">
          {/* Label + soru işareti */}
          <div className="flex items-center justify-between">
            <label className="text-xs text-slate-400">{info.label}</label>
            <InfoTooltip info={info} />
          </div>

          {/* Değer + slider */}
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={params[key]}
              min={info.min}
              max={info.max}
              step={info.step}
              onChange={(e) => set(key, parseFloat(e.target.value))}
              className="w-20 bg-slate-700 rounded px-2 py-1 text-sm text-right"
            />
            <input
              type="range"
              min={info.min}
              max={info.max}
              step={info.step}
              value={params[key]}
              onChange={(e) => set(key, parseFloat(e.target.value))}
              className="flex-1 accent-blue-500"
            />
          </div>

          {/* Hızlı preset butonlar */}
          <div className="flex gap-1 flex-wrap">
            {info.presets.map((p) => (
              <button
                key={p.label}
                onClick={() => set(key, p.value)}
                className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                  params[key] === p.value
                    ? "border-blue-500 text-blue-300 bg-blue-950"
                    : "border-slate-600 text-slate-400 hover:border-slate-400"
                }`}
              >
                {p.label} ({p.value})
              </button>
            ))}
          </div>
        </div>
      ))}

      {/* Pattern seçimi */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label className="text-xs text-slate-400">Pattern</label>
          <InfoTooltip
            info={{
              color: "slate",
              short: "Kaplama yolu şekli",
              detail: [
                "Zigzag: ileri-geri paralel çizgiler — en verimli ve hızlı",
                "Paralel: tek yönde gidip boş dönüş — zigzag'dan yavaş ama daha düzenli",
                "Spiral: dıştan içe döngü — köşeli parçalarda iyi çalışmaz",
              ],
            }}
          />
        </div>
        <div className="flex gap-2">
          {["zigzag", "parallel", "spiral"].map((p) => (
            <button
              key={p}
              onClick={() => set("pattern_type", p)}
              className={`flex-1 py-1 text-xs rounded border transition-colors capitalize ${
                params.pattern_type === p
                  ? "border-blue-500 text-blue-300 bg-blue-950"
                  : "border-slate-600 text-slate-400 hover:border-slate-400"
              }`}
            >
              {p === "zigzag" ? "Zigzag" : p === "parallel" ? "Paralel" : "Spiral"}
            </button>
          ))}
        </div>
      </div>

      {/* Sıfırla */}
      <button
        onClick={() =>
          onChange({
            line_spacing: 1.0,
            z_offset: 0.3,
            feed_rate: 600,
            travel_rate: 1500,
            band_thickness: 1.0,
            pattern_type: "zigzag",
          })
        }
        className="w-full text-xs py-1 rounded border border-slate-600 text-slate-400 hover:border-slate-400 hover:text-slate-200 transition-colors"
      >
        Varsayılana sıfırla
      </button>
    </div>
  );
}
