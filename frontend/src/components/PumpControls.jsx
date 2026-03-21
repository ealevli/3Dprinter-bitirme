import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";

export default function PumpControls({ onLog }) {
  const [rpm, setRpm] = useState(150);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [pumpPort, setPumpPort] = useState("");
  const [connectError, setConnectError] = useState("");

  useEffect(() => {
    fetchStatus();
    fetchPort();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
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
      if (res.data.rpm) setRpm(res.data.rpm);
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
      onLog?.(`Pompa başlatıldı (${rpm} adım/s).`);
    } catch (err) {
      onLog?.(`Pompa hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  async function handleStop() {
    try {
      await axios.post("/pump/stop");
      setRunning(false);
      onLog?.("Pompa durduruldu.");
    } catch (err) {
      onLog?.(`Pompa durdurma hatası: ${err.response?.data?.detail ?? err.message}`);
    }
  }

  async function handleSpeedChange(val) {
    setRpm(val);
    if (running) {
      await axios.post("/pump/speed", { rpm: val }).catch(() => {});
    }
  }

  return (
    <div className="bg-slate-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Pompa Kontrolü</h3>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            connected
              ? running
                ? "bg-green-900 text-green-300"
                : "bg-slate-700 text-slate-300"
              : "bg-red-900 text-red-300"
          }`}
        >
          {connected ? (running ? "Çalışıyor" : "Hazır") : "Bağlı değil"}
        </span>
      </div>

      {/* Not connected state */}
      {!connected && (
        <div className="space-y-2">
          {/* Step 1: go to Settings */}
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

          {/* Show configured port */}
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

          {/* Error feedback */}
          {connectError && (
            <p className="text-xs text-red-400 bg-red-950 rounded p-2">
              {connectError}
            </p>
          )}
        </div>
      )}

      {/* Connected state */}
      {connected && (
        <>
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
              onChange={(e) => handleSpeedChange(parseInt(e.target.value))}
              className="w-full accent-blue-500"
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleStart}
              disabled={running}
              className="flex-1 py-1.5 text-sm rounded bg-green-700 hover:bg-green-600 disabled:opacity-40 font-medium"
            >
              Başlat
            </button>
            <button
              onClick={handleStop}
              disabled={!running}
              className="flex-1 py-1.5 text-sm rounded bg-red-700 hover:bg-red-600 disabled:opacity-40 font-medium"
            >
              Durdur
            </button>
          </div>
        </>
      )}
    </div>
  );
}
