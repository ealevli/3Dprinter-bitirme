import { useState } from "react";

// ── Parametre tanımları ────────────────────────────────────────────────────────
// Her parametre için: ne işe yarar, nasıl ayarlanır, önerilen aralık
const PARAM_INFO = {
  line_spacing: {
    label: "Çizgi Aralığı / Hücre Boyutu (mm)",
    unit: "mm",
    min: 0.2,
    max: 20,
    step: 0.1,
    color: "blue",
    short: "Kaplama çizgileri arasındaki mesafe (Honeycomb için: iki kenar arası mesafe)",
    detail: [
      "Zigzag / Paralel: çizgiler arası boşluk (0.5–4 mm önerilir)",
      "Spiral: halkalar arası boşluk",
      "Honeycomb: karşılıklı iki kenar arası mesafe — 10 mm önerilen başlangıç",
      "Küçük değer → daha yoğun desen, daha uzun süre",
      "Büyük değer → seyrek desen, hızlı biter",
    ],
    presets: [
      { label: "Yoğun", value: 0.5 },
      { label: "Normal", value: 1.0 },
      { label: "Seyrek", value: 2.0 },
      { label: "Honeycomb 10mm", value: 10.0 },
    ],
  },
  z_offset: {
    label: "Z Boşluğu — Yüzey Üstü (mm)",
    unit: "mm",
    min: 0.1,
    max: 3,
    step: 0.05,
    color: "purple",
    short: "BLTouch parça yüzeyini ölçer — bu değer O yüzeyden kaç mm yukarıda kaplanacağını belirler",
    detail: [
      "Başlat'a basıldığında BLTouch otomatik olarak parça yüzeyini ölçer (G30)",
      "Bu değer = ölçülen yüzeyden YUKARI boşluk (bant kalınlığı dahil, ayrıca girme)",
      "0.2–0.4 mm → ideal: çözelti damlacık yapmadan yüzeye değer",
      "Çok az (< 0.2 mm) → nozzle yüzeye sürtebilir, parçaya zarar verir",
      "Çok fazla (> 0.8 mm) → çözelti damla damla akar, düzgün yayılmaz",
      "Bant kalınlığı artık ayrıca girilmesine gerek yok — BLTouch her şeyi ölçer",
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
    label: "Bant Kalınlığı (mm) — Manuel mod",
    unit: "mm",
    min: 0,
    max: 5,
    step: 0.1,
    color: "amber",
    short: "BLTouch modunda kullanılmaz — sadece Önizle'deki Z hesabını etkiler",
    detail: [
      "BLTouch (Başlat) modunda bu değer dikkate ALINMAZ",
      "BLTouch parça yüzeyini doğrudan ölçtüğü için bant kalınlığı otomatik hesaba katılır",
      "Bu değer yalnızca Önizle'deki Z hesabını (görsel) etkiler",
      "Gerçek kaplama Z BLTouch probe sonucuna göre belirlenir: Z_probe + Z_boşluğu",
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
                "Paralel: tek yönde gidip boş dönüş — düzenli tek yön",
                "Spiral: dıştan içe ofset halkalar — kontur takip eder",
                "Honeycomb: altıgen petek — Hücre Boyutu 10 mm (iki kenar arası)",
                "Çapraz: yatay + dikey çift tarama — ISO 2409 yapışma testi deseni",
                "Gradyan: altta yoğun üstte seyrek — tek parçada farklı yoğunluk karşılaştırması",
              ],
            }}
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {[
            { value: "zigzag",     label: "Zigzag"   },
            { value: "parallel",   label: "Paralel"  },
            { value: "spiral",     label: "Spiral"   },
            { value: "honeycomb",  label: "Honeycomb"},
            { value: "crosshatch", label: "Çapraz"   },
            { value: "gradient",   label: "Gradyan"  },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => {
                if (value === "honeycomb") {
                  onChange({ ...params, pattern_type: value, line_spacing: 10.0 });
                } else {
                  set("pattern_type", value);
                }
              }}
              className={`flex-1 py-1 text-xs rounded border transition-colors ${
                params.pattern_type === value
                  ? "border-blue-500 text-blue-300 bg-blue-950"
                  : "border-slate-600 text-slate-400 hover:border-slate-400"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Manuel Parça Boyutu */}
      <div className="border-t border-slate-700 pt-3 space-y-2">
        <div className="flex items-center gap-1">
          <p className="text-xs font-semibold text-green-400">Manuel Parça Boyutu (mm)</p>
          <InfoTooltip info={{
            color: "green",
            short: "Kamera ölçüsü yanlışsa cetvel ile ölçüp buraya gir",
            detail: [
              "İkisi de > 0 ise: tespit edilen kontur yerine bu boyutta dikdörtgen kullanılır",
              "Merkez: kameranın tespit ettiği parça merkezi (konum değişmez)",
              "Örn: 67mm × 42mm → yazıcı tam o boyutta kaplar",
              "0 bırakırsan kamera tespiti kullanılır",
              "Cetvel ile parçayı ölç → değerleri buraya gir → Önizle",
            ],
          }} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[
            { key: "manual_width_mm",  label: "Genişlik (mm)" },
            { key: "manual_height_mm", label: "Yükseklik (mm)" },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="text-xs text-slate-400 block mb-1">{label}</label>
              <input
                type="number"
                value={params[key] ?? 0}
                min={0}
                max={220}
                step={0.5}
                onChange={(e) => set(key, parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-700 rounded px-2 py-1 text-sm text-right"
                placeholder="0 = kamera"
              />
            </div>
          ))}
        </div>
        {(params.manual_width_mm > 0 && params.manual_height_mm > 0) && (
          <p className="text-xs text-green-400 bg-green-950 border border-green-800 rounded p-2">
            ✓ Manuel boyut aktif: {params.manual_width_mm} × {params.manual_height_mm} mm dikdörtgen kullanılıyor.
          </p>
        )}
        {(params.manual_width_mm > 0) !== (params.manual_height_mm > 0) && (
          <p className="text-xs text-amber-400">⚠ İkisini de gir (genişlik VE yükseklik).</p>
        )}
      </div>

      {/* Kontur İçe Çekme */}
      <div className="border-t border-slate-700 pt-3 space-y-2">
        <div className="flex items-center gap-1">
          <p className="text-xs font-semibold text-cyan-400">Kontur Kenar Payı (mm)</p>
          <InfoTooltip info={{
            color: "slate",
            short: "Tespit edilen parça sınırından ne kadar içeri çekilsin",
            detail: [
              "Pozitif değer → kaplama yolu parça kenarından içeri çekilir",
              "Örn: 2mm → kaplama parçanın 2mm iç kısmından başlar",
              "Bant/yapıştırıcı üzerine çözelti dökülmesini önler",
              "Yazıcı fazla alan kaplıyorsa bu değeri artır",
              "Tipik değer: 1–3 mm",
              "Negatif değer → dışa doğru genişletir (genellikle gereksiz)",
            ],
          }} />
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={params.contour_inset_mm ?? 0}
            min={-5}
            max={20}
            step={0.5}
            onChange={(e) => set("contour_inset_mm", parseFloat(e.target.value) || 0)}
            className="w-20 bg-slate-700 rounded px-2 py-1 text-sm text-right"
          />
          <div className="flex gap-1 flex-wrap flex-1">
            {[0, 1, 2, 3, 5].map((v) => (
              <button
                key={v}
                onClick={() => set("contour_inset_mm", v)}
                className={`flex-1 text-xs py-0.5 rounded border transition-colors ${
                  (params.contour_inset_mm ?? 0) === v
                    ? "border-cyan-500 text-cyan-300 bg-cyan-950"
                    : "border-slate-600 text-slate-400 hover:border-slate-400"
                }`}
              >
                {v === 0 ? "Kapalı" : `${v}mm`}
              </button>
            ))}
          </div>
        </div>
        {(params.contour_inset_mm ?? 0) > 0 && (
          <p className="text-xs text-cyan-400 bg-cyan-950 border border-cyan-800 rounded p-2">
            Kaplama yolu parça kenarından {params.contour_inset_mm}mm içeride başlayacak.
          </p>
        )}
      </div>

      {/* XY Kalibrasyon Düzeltmesi */}
      <div className="border-t border-slate-700 pt-3 space-y-2">
        <div className="flex items-center gap-1">
          <p className="text-xs font-semibold text-amber-400">XY Kalibrasyon Düzeltmesi</p>
          <InfoTooltip info={{
            color: "amber",
            short: "Yazıcı parçanın yanına değil biraz uzağa gidiyorsa buradan düzelt",
            detail: [
              "ArUco kalibrasyonu mükemmel olmayabilir → yazıcı sistematik olarak kayabilir",
              "Y Düzeltme > 0: yazıcı parçanın önüne (düşük Y'ye) gidiyorsa artır",
              "Y Düzeltme < 0: yazıcı parçanın arkasına (yüksek Y'ye) gidiyorsa azalt",
              "X Düzeltme: sol/sağ kayma için aynı mantık",
              "Adım adım: 2mm dene → daha iyi mi? → artır/azalt",
              "Kalıcı çözüm: Ayarlar → marker pozisyonlarını ölç → yeniden kalibre et",
            ],
          }} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[
            { key: "x_offset_mm", label: "X Düzeltme (mm)" },
            { key: "y_offset_mm", label: "Y Düzeltme (mm)" },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="text-xs text-slate-400 block mb-1">{label}</label>
              <input
                type="number"
                value={params[key] ?? 0}
                min={-30}
                max={30}
                step={0.5}
                onChange={(e) => set(key, parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-700 rounded px-2 py-1 text-sm text-right"
              />
              <div className="flex gap-1 mt-1 flex-wrap">
                {[-5, -2, -1, 0, 1, 2, 5].map((v) => (
                  <button
                    key={v}
                    onClick={() => set(key, v)}
                    className={`flex-1 text-xs py-0.5 rounded border transition-colors ${
                      (params[key] ?? 0) === v
                        ? "border-amber-500 text-amber-300 bg-amber-950"
                        : "border-slate-600 text-slate-400 hover:border-slate-400"
                    }`}
                  >
                    {v > 0 ? `+${v}` : v}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        {((params.x_offset_mm ?? 0) !== 0 || (params.y_offset_mm ?? 0) !== 0) && (
          <p className="text-xs text-amber-400 bg-amber-950 border border-amber-800 rounded p-2">
            ⚠ Aktif: X{params.x_offset_mm >= 0 ? "+" : ""}{params.x_offset_mm ?? 0}mm,
            Y{params.y_offset_mm >= 0 ? "+" : ""}{params.y_offset_mm ?? 0}mm — tüm koordinatlara ekleniyor.
          </p>
        )}
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
            x_offset_mm: 0.0,
            y_offset_mm: 0.0,
            contour_inset_mm: 0.0,
            manual_width_mm: 0.0,
            manual_height_mm: 0.0,
          })
        }
        className="w-full text-xs py-1 rounded border border-slate-600 text-slate-400 hover:border-slate-400 hover:text-slate-200 transition-colors"
      >
        Varsayılana sıfırla
      </button>
    </div>
  );
}
