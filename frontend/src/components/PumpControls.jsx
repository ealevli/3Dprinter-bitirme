import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import axios from "axios";

export default function PumpControls({ onLog }) {
  const [rpm,        setRpm]        = useState(150);
  const [running,    setRunning]    = useState(false);
  const [connected,  setConnected]  = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [pumpPort,   setPumpPort]   = useState("");
  const [connectError, setConnectError] = useState("");
  const [direction,  setDirection]  = useState("fwd");   // "fwd" | "rev"
  const [priming,    setPriming]    = useState(false);
  const [primeSteps, setPrimeSteps] = useState(500);

  // Debounce için: slider bırakılınca (pointerUp) gönder
  const pendingRpm = useRef(rpm);

  useEffect(() => {
    fetchStatus();
    fetchPort();
  }, []);

  async function fetchPort() {
    const res = await axios.get("/system/config").catch(() => null);
    if (res) setPumpPort(res.data.pump_port ?? "");
  }

  async function fetchStatus() {
    const res = await axios.get("/pump/status").catch(() => null);
    if (res) {
      setRunning(res.data.running);
      setConnected(res.data.connected);
      if (res.data.rpm)       setRpm(res.data.rpm);
      if (res.data.direction) setDirection(res.data.direction);
    }
  }

  async function handleConnect() {
    setConnecting(true);
    setConnectError("");
    try {
      const res = await axios.post("/pump/connect");
      setConnected(true);
      onLog?.(`✓ ${res.data.message}`);
    } catch (err) {
      const msg = err.response?.data?.detail ?? err.message;
      setConnectError(msg);
      onLog?.(`Arduino bağlantı hatası: ${msg}`);
    } finally {
      setConnecting(false);
      fetchStatus();
      fetchPort();
    }
  }

  async function handleStart() {
    try {
      await axios.post("/pump/start", { rpm });
      setRunning(true);
      onLog?.(`Pompa başlatıldı (${rpm} adım/s, ${direction === "fwd" ? "ileri" : "geri"}).`);
    } catch (err) {
      onLog?.(`Pompa hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  async function handleStop() {
    try {
      await axios.post("/pump/stop");
      setRunning(false);
      setPriming(false);
      onLog?.("Pompa durduruldu.");
    } catch (err) {
      onLog?.(`Pompa durdurma hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  // Slider sürüklenirken sadece local state güncelle
  function handleSliderChange(val) {
    pendingRpm.current = val;
    setRpm(val);
  }

  // Slider bırakılınca backend'e gönder (debounce yerine pointerUp)
  async function handleSliderCommit() {
    if (running) {
      await axios.post("/pump/speed", { rpm: pendingRpm.current }).catch(() => {});
    }
  }

  async function handleDirectionToggle() {
    const newFwd = direction !== "fwd";
    try {
      await axios.post("/pump/direction", { forward: newFwd });
      setDirection(newFwd ? "fwd" : "rev");
      onLog?.(`Yön: ${newFwd ? "İleri (kaplama)" : "Geri (geri çekme)"}`);
    } catch (err) {
      onLog?.(`Yön hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  async function handlePrime() {
    setPriming(true);
    try {
      await axios.post("/pump/prime", { steps: primeSteps });
      onLog?.(`Prime başlatıldı (${primeSteps} adım).`);
      // 2 saniye sonra durduğunu varsay (UI için)
      setTimeout(() => setPriming(false), (primeSteps / rpm) * 1000 + 500);
    } catch (err) {
      setPriming(false);
      onLog?.(`Prime hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  return (
    <div className="bg-slate-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Pompa Kontrolü</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            connected
              ? running || priming
                ? "bg-green-900 text-green-300"
                : "bg-slate-700 text-slate-300"
              : "bg-red-900 text-red-300"
          }`}
        >
          {connected
            ? running
              ? "Çalışıyor"
              : priming
              ? "Prime…"
              : "Hazır"
            : "Bağlı değil"}
        </span>
      </div>

      {/* Bağlı değil */}
      {!connected && (
        <div className="space-y-2">
          <div className="bg-slate-700 rounded p-2 text-xs text-slate-300 space-y-1">
            <p className="font-medium text-slate-200">Bağlanmak için:</p>
            <p>
              1.{" "}
              <Link to="/ayarlar" className="text-blue-400 underline hover:text-blue-300">
                Ayarlar
              </Link>{" "}
              → Arduino Portunu seç → Kaydet
            </p>
            <p>2. Aşağıdaki butona bas</p>
          </div>
          {pumpPort ? (
            <p className="text-xs text-slate-400">
              Kayıtlı port:{" "}
              <span className="font-mono text-slate-200">{pumpPort}</span>
            </p>
          ) : (
            <p className="text-xs text-amber-400">
              ⚠ Port seçilmemiş — önce Ayarlar'a git
            </p>
          )}
          <button
            onClick={handleConnect}
            disabled={connecting || !pumpPort}
            className="w-full py-1.5 text-sm rounded bg-amber-700 hover:bg-amber-600 disabled:opacity-50 font-medium"
          >
            {connecting ? "Bağlanıyor…" : "Arduino'ya Bağlan"}
          </button>
          {connectError && (
            <p className="text-xs text-red-400 bg-red-950 rounded p-2">{connectError}</p>
          )}
        </div>
      )}

      {/* Bağlı */}
      {connected && (
        <>
          {/* Hız slider */}
          <div>
            <label className="text-xs text-slate-400 block mb-1">
              Hız: <strong>{rpm}</strong> adım/s
            </label>
            <input
              type="range"
              min={10}
              max={500}
              step={10}
              value={rpm}
              onChange={(e) => handleSliderChange(parseInt(e.target.value))}
              onPointerUp={handleSliderCommit}
              onMouseUp={handleSliderCommit}
              className="w-full accent-blue-500"
            />
            <div className="flex justify-between text-xs text-slate-500 mt-0.5">
              <span>10</span>
              <span>500</span>
            </div>
          </div>

          {/* Yön */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 flex-1">Yön:</span>
            <button
              onClick={handleDirectionToggle}
              disabled={running}
              className={`flex-1 py-1 text-xs rounded border transition-colors disabled:opacity-40 ${
                direction === "fwd"
                  ? "border-blue-500 text-blue-300 bg-blue-950"
                  : "border-orange-500 text-orange-300 bg-orange-950"
              }`}
            >
              {direction === "fwd" ? "▶ İleri" : "◀ Geri"}
            </button>
          </div>

          {/* Başlat / Durdur */}
          <div className="flex gap-2">
            <button
              onClick={handleStart}
              disabled={running || priming}
              className="flex-1 py-1.5 text-sm rounded bg-green-700 hover:bg-green-600 disabled:opacity-40 font-medium"
            >
              Başlat
            </button>
            <button
              onClick={handleStop}
              disabled={!running && !priming}
              className="flex-1 py-1.5 text-sm rounded bg-red-700 hover:bg-red-600 disabled:opacity-40 font-medium"
            >
              Durdur
            </button>
          </div>

          {/* Prime */}
          <div className="border-t border-slate-700 pt-2 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 flex-1">Prime adım:</span>
              <input
                type="number"
                min={50}
                max={5000}
                step={50}
                value={primeSteps}
                onChange={(e) => setPrimeSteps(parseInt(e.target.value))}
                className="w-20 bg-slate-700 rounded px-2 py-1 text-xs text-right"
              />
            </div>
            <button
              onClick={handlePrime}
              disabled={running || priming}
              className="w-full py-1.5 text-xs rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-40 font-medium"
            >
              {priming ? "Prime…" : "Prime (hortumu doldur)"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
