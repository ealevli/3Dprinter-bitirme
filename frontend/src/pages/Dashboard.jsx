import { useState, useCallback, useRef, useEffect } from "react";
import CameraFeed from "../components/CameraFeed";
import GCodePreview from "../components/GCodePreview";
import PumpControls from "../components/PumpControls";
import CoatingParams from "../components/CoatingParams";
import PrinterJog from "../components/PrinterJog";
import axios from "axios";

/** Shows detected part dimensions below the camera feed. */
function DetectionInfo({ detection }) {
  const { bbox, contour_mm, contour_px, calibrated, method, markers_found } = detection;

  // Pixel dimensions from bbox
  const [, , bw, bh] = bbox ?? [0, 0, 0, 0];

  // mm dimensions from contour_mm bounding box
  let mmW = null, mmH = null;
  if (contour_mm?.length) {
    const xs = contour_mm.map((p) => p[0]);
    const ys = contour_mm.map((p) => p[1]);
    mmW = (Math.max(...xs) - Math.min(...xs)).toFixed(1);
    mmH = (Math.max(...ys) - Math.min(...ys)).toFixed(1);
  }

  const Chip = ({ label, value, color = "text-slate-300" }) => (
    <span>
      <span className="text-slate-500">{label}: </span>
      <span className={`font-mono font-semibold ${color}`}>{value}</span>
    </span>
  );

  return (
    <>
      {mmW && mmH ? (
        <Chip label="Boyut" value={`${mmW} × ${mmH} mm`} color="text-green-400" />
      ) : (
        <Chip label="Boyut (px)" value={`${bw} × ${bh} px`} color="text-amber-400" />
      )}
      <Chip label="Kontur" value={`${contour_px?.length ?? 0} nokta`} />
      <Chip
        label="Marker"
        value={`${markers_found ?? 0}/4`}
        color={markers_found >= 4 ? "text-green-400" : markers_found > 0 ? "text-amber-400" : "text-red-400"}
      />
      <Chip
        label="Kalibrasyon"
        value={calibrated ? "✓" : "✗ Gerekli"}
        color={calibrated ? "text-green-400" : "text-red-400"}
      />
      <Chip label="Yöntem" value={method ?? "-"} color="text-cyan-400" />
    </>
  );
}

export default function Dashboard() {
  const [logs, setLogs] = useState([]);
  const [detection, setDetection] = useState(null);
  const [gcodeResult, setGcodeResult] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [jobStatus, setJobStatus] = useState(null);
  const [showGcode, setShowGcode] = useState(false);
  const previewRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const [bgExists, setBgExists] = useState(false);

  useEffect(() => {
    axios.get("/camera/background").then(r => setBgExists(r.data.exists)).catch(() => {});
  }, []);

  async function handleSaveBg() {
    try {
      const res = await axios.post("/camera/background");
      setBgExists(true);
      addLog(res.data.message);
    } catch (err) {
      addLog(`Arka plan hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  async function handleDeleteBg() {
    try {
      const res = await axios.delete("/camera/background");
      setBgExists(false);
      addLog(res.data.message);
    } catch (err) {
      addLog(`Silme hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  // Auto-scroll to G-code preview when it appears
  useEffect(() => {
    if (gcodeResult && previewRef.current) {
      previewRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [gcodeResult]);

  const [params, setParams] = useState({
    line_spacing: 1.0,
    z_offset: 0.3,
    feed_rate: 600,
    travel_rate: 1500,
    band_thickness: 1.0,
    pattern_type: "zigzag",
  });

  const addLog = useCallback((msg) => {
    const ts = new Date().toLocaleTimeString("tr-TR");
    setLogs((prev) => [`[${ts}] ${msg}`, ...prev].slice(0, 50));
  }, []);

  // ── Tara ────────────────────────────────────────────────────────────────
  async function handleScan() {
    setIsScanning(true);
    try {
      const res = await axios.post("/detect/preview");
      setDetection(res.data);
      if (res.data.contour_mm?.length) {
        addLog(
          `Parça tespit edildi (${res.data.method}). Kontur: ${res.data.contour_mm.length} nokta` +
            (res.data.class_name
              ? `, sınıf: ${res.data.class_name} (${(res.data.confidence * 100).toFixed(0)}%)`
              : "")
        );
      } else {
        addLog("Parça bulunamadı veya kalibrasyon gerekli.");
      }
    } catch (err) {
      addLog(`Tarama hatası: ${err.response?.data?.detail ?? err.message}`);
    } finally {
      setIsScanning(false);
    }
  }

  // Her zaman güncel değerlere erişmek için ref'ler
  const paramsRef    = useRef(params);
  const detectionRef = useRef(detection);
  const gcodeOpenRef = useRef(!!gcodeResult);
  paramsRef.current    = params;
  detectionRef.current = detection;
  gcodeOpenRef.current = !!gcodeResult;

  // Önizleme üretici — hem manuel hem otomatik çağrı için
  const generatePreview = useCallback(async (silent = false) => {
    const det = detectionRef.current;
    const prm = paramsRef.current;
    if (!det?.contour_px?.length) {
      if (!silent) addLog("Önce Tara'ya basın.");
      return;
    }
    if (!det?.contour_mm?.length) {
      if (!silent) addLog("⚠️ Kalibrasyon gerekli — Ayarlar → Kalibre Et.");
      return;
    }
    try {
      const start_gcode = localStorage.getItem("cfg_start_gcode") || undefined;
      const end_gcode   = localStorage.getItem("cfg_end_gcode")   || undefined;
      const res = await axios.post("/gcode/generate", {
        contour_mm: det.contour_mm,
        ...prm,
        start_gcode,
        end_gcode,
      });
      setGcodeResult(res.data);
      if (!silent) addLog(
        `G-code üretildi: ${res.data.line_count} satır, ~${Math.round(res.data.estimated_time_s)}s`
      );
    } catch (err) {
      if (!silent) addLog(`G-code hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }, [addLog]);

  // Manuel "Önizle" butonu
  const handlePreview = useCallback(() => generatePreview(false), [generatePreview]);

  // Parametre değişince önizlemeyi debounce ile otomatik güncelle
  useEffect(() => {
    if (!gcodeOpenRef.current) return;   // önizleme kapalıysa yapma
    const timer = setTimeout(() => {
      generatePreview(true);
    }, 350);                             // 350ms bekle — slider sürüklenirken spam olmasın
    return () => clearTimeout(timer);
  }, [params, generatePreview]);

  // ── Başlat ──────────────────────────────────────────────────────────────
  async function handleStart() {
    if (!gcodeResult?.gcode) {
      addLog("Önce önizleme oluşturun.");
      return;
    }
    setIsSending(true);
    try {
      const res = await axios.post("/gcode/send", { gcode: gcodeResult.gcode });
      addLog(`G-code gönderimi başladı. Job: ${res.data.job_id}`);
      pollStatus();
    } catch (err) {
      addLog(`Gönderim hatası: ${err.response?.data?.detail ?? err.message}`);
      setIsSending(false);
    }
  }

  function pollStatus() {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await axios.get("/gcode/status");
        setJobStatus(res.data);
        const st = res.data.status;
        const stop = () => {
          setIsSending(false);
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        };
        if (st === "done") {
          addLog("Kaplama tamamlandı.");
          stop();
        } else if (st === "stopped") {
          addLog(`Durduruldu (${res.data.current_line}/${res.data.total_lines} satır gönderildi).`);
          stop();
        } else if (st === "error") {
          const detail = res.data.last_error ? ` — ${res.data.last_error}` : "";
          addLog(`Gönderim hatası (satır ${res.data.current_line}/${res.data.total_lines})${detail}`);
          stop();
        } else if (st === "idle" && res.data.total_lines === 0) {
          // Backend restarted mid-send (hot reload / crash) — unlock UI
          addLog("Bağlantı kesildi veya backend yeniden başladı. Yazıcıyı yeniden bağlayın.");
          stop();
        }
      } catch {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        setIsSending(false);
      }
    }, 1000);
  }

  async function handleStop() {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    await axios.post("/gcode/stop").catch(() => {});
    setIsSending(false);
    addLog("Durdurma komutu gönderildi.");
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Main row */}
      <div className="flex gap-4">
        {/* Left: camera + preview */}
        <div className="flex-1 flex flex-col gap-3">
          <div className="relative bg-slate-900 rounded-lg overflow-hidden" style={{ height: 420 }}>
            <CameraFeed
              detectionImage={detection?.image}
              onClearDetection={() => setDetection(null)}
            />
          </div>

          {/* Detection info panel */}
          {detection?.bbox && (
            <div className="bg-slate-800 rounded-lg px-4 py-2 flex flex-wrap gap-x-6 gap-y-1 text-xs">
              <DetectionInfo detection={detection} />
            </div>
          )}

          {gcodeResult && (
            <div ref={previewRef} className="bg-slate-900 rounded-lg overflow-hidden border border-slate-700">
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-700">
                <span className="text-xs text-slate-400 font-medium">
                  G-code Önizleme — {gcodeResult.line_count} satır
                  {gcodeResult.estimated_time_s > 0 && ` · ~${Math.round(gcodeResult.estimated_time_s)}s`}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowGcode((v) => !v)}
                    className="text-xs text-slate-400 hover:text-slate-200 border border-slate-600 rounded px-2 py-0.5"
                  >
                    {showGcode ? "Kodu Gizle" : "G-code"}
                  </button>
                  <button
                    onClick={() => { setGcodeResult(null); setShowGcode(false); }}
                    className="text-xs text-slate-500 hover:text-slate-300"
                  >✕</button>
                </div>
              </div>
              <div style={{ height: 240 }}>
                <GCodePreview
                  paths={gcodeResult.paths ?? []}
                  wallPaths={gcodeResult.wall_paths ?? []}
                  contourMm={detection?.contour_mm ?? []}
                />
              </div>
              {showGcode && (
                <div className="border-t border-slate-700">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800">
                    <span className="text-xs text-slate-400 font-medium">Ham G-code</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(gcodeResult.gcode)}
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      Kopyala
                    </button>
                  </div>
                  <textarea
                    readOnly
                    value={gcodeResult.gcode}
                    className="w-full bg-slate-950 text-slate-300 text-xs font-mono px-3 py-2 resize-none focus:outline-none"
                    style={{ height: 220 }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Background controls */}
          <div className="flex gap-3">
            <button
              onClick={handleSaveBg}
              className="flex-1 py-2 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 font-semibold text-sm flex justify-between items-center px-4 transition-colors"
            >
              <span className="text-slate-300">📸 Boş Tablayı Tanıt</span>
              {bgExists && <span className="text-green-400 text-xs">✔ Kayıtlı</span>}
            </button>
            {bgExists && (
              <button
                onClick={handleDeleteBg}
                className="px-4 py-2 rounded bg-slate-800 hover:bg-red-900/40 text-slate-400 hover:text-red-400 font-semibold text-sm transition-colors border border-slate-700"
              >
                Sil
              </button>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleScan}
              disabled={isScanning}
              className="flex-1 py-2 rounded bg-sky-600 hover:bg-sky-500 disabled:opacity-50 font-semibold text-sm transition-colors"
            >
              {isScanning ? "Taranıyor…" : "Tara"}
            </button>
            <button
              onClick={handlePreview}
              disabled={!detection?.contour_px?.length}
              title={!detection?.calibrated ? "Kalibrasyon yapılmamış — mm koordinatı yok, piksel koordinatıyla devam edilecek" : ""}
              className="flex-1 py-2 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 font-semibold text-sm transition-colors"
            >
              Önizle
            </button>
            {isSending ? (
              <button
                onClick={handleStop}
                className="flex-1 py-2 rounded bg-red-600 hover:bg-red-500 font-semibold text-sm transition-colors"
              >
                Durdur
              </button>
            ) : (
              <button
                onClick={handleStart}
                disabled={!gcodeResult}
                className="flex-1 py-2 rounded bg-green-600 hover:bg-green-500 disabled:opacity-50 font-semibold text-sm transition-colors"
              >
                Başlat
              </button>
            )}
          </div>

          {/* Progress bar */}
          {jobStatus && isSending && (
            <div className="bg-slate-800 rounded p-2">
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Gönderiliyor…</span>
                <span>
                  {jobStatus.current_line} / {jobStatus.total_lines} satır
                </span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full">
                <div
                  className="h-2 bg-green-500 rounded-full transition-all"
                  style={{
                    width: jobStatus.total_lines
                      ? `${(jobStatus.current_line / jobStatus.total_lines) * 100}%`
                      : "0%",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Right: controls */}
        <div className="w-64 flex flex-col gap-3">
          <PumpControls onLog={addLog} />
          <PrinterJog onLog={addLog} />
          <CoatingParams params={params} onChange={setParams} />
        </div>
      </div>

      {/* Log area */}
      <div className="bg-slate-900 rounded-lg p-3 h-36 overflow-y-auto font-mono text-xs text-slate-300 space-y-0.5">
        {logs.length === 0 && (
          <p className="text-slate-500">Sistem hazır. "Tara" ile başlayın.</p>
        )}
        {logs.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </div>
    </div>
  );
}
