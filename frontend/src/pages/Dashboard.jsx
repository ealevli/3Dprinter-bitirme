import { useState, useCallback } from "react";
import CameraFeed from "../components/CameraFeed";
import GCodePreview from "../components/GCodePreview";
import PumpControls from "../components/PumpControls";
import CoatingParams from "../components/CoatingParams";
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
          `Parça tespit edildi. Kontur noktaları: ${res.data.contour_mm.length}` +
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

  // ── Önizle ──────────────────────────────────────────────────────────────
  async function handlePreview() {
    if (!detection?.contour_px?.length) {
      addLog("Önce Tara'ya basın.");
      return;
    }
    if (!detection?.contour_mm?.length) {
      addLog("⚠️ Kalibrasyon yapılmamış — Ayarlar → Kalibre Et butonuna bas, sonra tekrar Tara + Önizle yap.");
      return;
    }
    try {
      const res = await axios.post("/gcode/generate", {
        contour_mm: detection.contour_mm,
        ...params,
      });
      setGcodeResult(res.data);
      addLog(
        `G-code üretildi: ${res.data.line_count} satır, tahmini süre: ${Math.round(res.data.estimated_time_s)}s`
      );
    } catch (err) {
      addLog(`G-code hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

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
    const interval = setInterval(async () => {
      try {
        const res = await axios.get("/gcode/status");
        setJobStatus(res.data);
        if (res.data.status === "done") {
          addLog("Kaplama tamamlandı.");
          setIsSending(false);
          clearInterval(interval);
        } else if (res.data.status === "error") {
          addLog("Gönderim sırasında hata oluştu.");
          setIsSending(false);
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
        setIsSending(false);
      }
    }, 1000);
  }

  async function handleStop() {
    await axios.post("/gcode/stop").catch(() => {});
    setIsSending(false);
    addLog("Durdurma komutu gönderildi (M112).");
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
            <div className="bg-slate-900 rounded-lg overflow-hidden" style={{ height: 200 }}>
              <GCodePreview paths={gcodeResult.paths} />
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleScan}
              disabled={isScanning}
              className="flex-1 py-2 rounded bg-sky-600 hover:bg-sky-500 disabled:opacity-50 font-semibold text-sm"
            >
              {isScanning ? "Taranıyor…" : "Tara"}
            </button>
            <button
              onClick={handlePreview}
              disabled={!detection?.contour_px?.length}
              title={!detection?.calibrated ? "Kalibrasyon yapılmamış — mm koordinatı yok, piksel koordinatıyla devam edilecek" : ""}
              className="flex-1 py-2 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 font-semibold text-sm"
            >
              Önizle
            </button>
            {isSending ? (
              <button
                onClick={handleStop}
                className="flex-1 py-2 rounded bg-red-600 hover:bg-red-500 font-semibold text-sm"
              >
                Durdur
              </button>
            ) : (
              <button
                onClick={handleStart}
                disabled={!gcodeResult}
                className="flex-1 py-2 rounded bg-green-600 hover:bg-green-500 disabled:opacity-50 font-semibold text-sm"
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
