import { useState, useEffect } from "react";
import axios from "axios";

export default function Settings() {
  const [ports, setPorts] = useState([]);
  const [status, setStatus] = useState({
    camera: "...", printer: "...", pump: "...", calibration: "...",
  });
  const [config, setConfig] = useState({
    printer_port: "",
    printer_baudrate: 115200,
    pump_port: "",
    pump_baudrate: 9600,
    camera_index: 0,
  });
  const [markerPositions, setMarkerPositions] = useState({
    0: [10, 10],
    1: [210, 10],
    2: [210, 210],
    3: [10, 210],
  });
  const [saved, setSaved] = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [calibResult, setCalibResult] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [foundCameras, setFoundCameras] = useState(null);

  useEffect(() => {
    fetchPorts();
    fetchStatus();
    fetchConfig();
  }, []);

  async function fetchConfig() {
    const res = await axios.get("/system/config").catch(() => null);
    if (!res) return;
    const d = res.data;
    setConfig({
      printer_port: d.printer_port ?? "",
      printer_baudrate: d.printer_baudrate ?? 115200,
      pump_port: d.pump_port ?? "",
      pump_baudrate: d.pump_baudrate ?? 9600,
      camera_index: d.camera_index ?? 0,
    });
    if (d.aruco_marker_positions_mm) {
      setMarkerPositions(
        Object.fromEntries(
          Object.entries(d.aruco_marker_positions_mm).map(([k, v]) => [k, v])
        )
      );
    }
  }

  async function fetchPorts() {
    const res = await axios.get("/system/ports").catch(() => null);
    if (res) setPorts(res.data.ports);
  }

  async function fetchStatus() {
    const res = await axios.get("/system/status").catch(() => null);
    if (res) setStatus(res.data);
    else setStatus({ camera: "hata", printer: "hata", pump: "hata", calibration: "hata" });
  }

  async function handleSave() {
    const prevIndex = parseInt(localStorage.getItem("camera_index") ?? "0");
    const payload = {
      ...config,
      aruco_marker_positions_mm: Object.fromEntries(
        Object.entries(markerPositions).map(([k, v]) => [k, v])
      ),
    };
    await axios.post("/system/config", payload).catch(() => {});
    // Persist camera index so Dashboard's CameraFeed can pick up the change.
    localStorage.setItem("camera_index", config.camera_index);
    if (config.camera_index !== prevIndex) {
      // Notify other tabs/components that the camera index changed.
      window.dispatchEvent(new CustomEvent("camera-index-changed"));
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    fetchStatus();
  }

  async function handleCalibrate() {
    setCalibrating(true);
    setCalibResult(null);
    try {
      const res = await axios.post("/camera/calibrate");
      setCalibResult({ success: true, msg: "Kalibrasyon başarılı." });
    } catch (err) {
      setCalibResult({
        success: false,
        msg: err.response?.data?.detail ?? "Kalibrasyon başarısız.",
      });
    } finally {
      setCalibrating(false);
      fetchStatus();
    }
  }

  function StatusBadge({ value }) {
    const ok = value === "ok";
    return (
      <span
        className={`px-2 py-0.5 rounded text-xs font-medium ${
          ok ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"
        }`}
      >
        {ok ? "Bağlı" : value}
      </span>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold">Ayarlar</h1>

      {/* Connection status — always visible */}
      <div className="bg-slate-800 rounded-lg p-4 space-y-2">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-semibold text-sm text-slate-300">Bağlantı Durumu</h2>
          <button onClick={fetchStatus} className="text-xs text-slate-400 hover:text-white">Yenile</button>
        </div>
        {Object.entries(status).map(([k, v]) => (
          <div key={k} className="flex items-center justify-between text-sm">
            <span className="capitalize text-slate-400">{k}</span>
            <StatusBadge value={v} />
          </div>
        ))}
      </div>

      {/* Serial ports */}
      <div className="bg-slate-800 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-sm text-slate-300">Serial Port Ayarları</h2>
          <button onClick={fetchPorts} className="text-xs text-slate-400 hover:text-white">
            Yenile
          </button>
        </div>

        {[
          { label: "Yazıcı Portu", key: "printer_port" },
          { label: "Arduino Portu", key: "pump_port" },
        ].map(({ label, key }) => (
          <div key={key}>
            <label className="block text-xs text-slate-400 mb-1">{label}</label>
            <select
              value={config[key]}
              onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
              className="w-full bg-slate-700 rounded px-3 py-1.5 text-sm"
            >
              <option value="">-- Seçin --</option>
              {ports.map((p) => (
                <option key={p.device} value={p.device}>
                  {p.device} — {p.description}
                </option>
              ))}
            </select>
          </div>
        ))}

        <div className="space-y-2">
          <label className="block text-xs text-slate-400">Kamera İndeksi</label>
          <div className="flex items-center gap-3 flex-wrap">
            <input
              type="number"
              min={0}
              value={config.camera_index}
              onChange={(e) =>
                setConfig({ ...config, camera_index: parseInt(e.target.value) })
              }
              className="w-24 bg-slate-700 rounded px-3 py-1.5 text-sm"
            />
            <button
              onClick={async () => {
                setScanning(true);
                setFoundCameras(null);
                const res = await axios.get("/camera/scan").catch(() => null);
                setFoundCameras(res?.data?.cameras ?? []);
                setScanning(false);
              }}
              disabled={scanning}
              className="px-3 py-1.5 text-xs rounded bg-slate-600 hover:bg-slate-500 disabled:opacity-50"
            >
              {scanning ? "Taranıyor…" : "Kameraları Tara"}
            </button>
          </div>

          {/* Scan results */}
          {scanning && (
            <p className="text-xs text-slate-400">0–7 arası indeksler deneniyor…</p>
          )}
          {foundCameras !== null && (
            <div className="space-y-1">
              {foundCameras.length === 0 ? (
                <p className="text-xs text-red-400">Hiç kamera bulunamadı.</p>
              ) : (
                foundCameras.map((cam) => (
                  <div key={cam.index} className="flex items-center gap-2">
                    <span className={`text-xs ${cam.readable ? "text-green-400" : "text-amber-400"}`}>
                      {cam.readable ? "✓" : "⚠"}
                    </span>
                    <span className="text-xs text-slate-300">
                      İndeks {cam.index} — {cam.readable ? "görüntü alınıyor" : "açıldı ama frame yok"}
                    </span>
                    <button
                      onClick={() => setConfig({ ...config, camera_index: cam.index })}
                      className="text-xs text-blue-400 hover:text-blue-300 underline"
                    >
                      Seç
                    </button>
                  </div>
                ))
              )}
              <p className="text-xs text-slate-500 pt-1">
                "Seç" butonuna basıp ardından Kaydet'e bas.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ArUco marker positions */}
      <div className="bg-slate-800 rounded-lg p-4 space-y-3">
        <h2 className="font-semibold text-sm text-slate-300">ArUco Marker Pozisyonları (mm)</h2>
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(markerPositions).map(([id, [x, y]]) => (
            <div key={id} className="flex items-center gap-2 text-sm">
              <span className="text-slate-400 w-16">Marker {id}</span>
              <input
                type="number"
                value={x}
                onChange={(e) =>
                  setMarkerPositions({
                    ...markerPositions,
                    [id]: [parseFloat(e.target.value), y],
                  })
                }
                className="w-20 bg-slate-700 rounded px-2 py-1 text-sm"
                placeholder="X"
              />
              <input
                type="number"
                value={y}
                onChange={(e) =>
                  setMarkerPositions({
                    ...markerPositions,
                    [id]: [x, parseFloat(e.target.value)],
                  })
                }
                className="w-20 bg-slate-700 rounded px-2 py-1 text-sm"
                placeholder="Y"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Calibration */}
      <div className="bg-slate-800 rounded-lg p-4 space-y-3">
        <h2 className="font-semibold text-sm text-slate-300">Kalibrasyon</h2>
        <p className="text-xs text-slate-400">
          Tablaya ArUco marker'lar yapıştırıldıktan sonra kalibre et.
        </p>
        <button
          onClick={handleCalibrate}
          disabled={calibrating}
          className="px-4 py-2 rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-sm font-medium"
        >
          {calibrating ? "Kalibre ediliyor…" : "Kalibre Et"}
        </button>
        {calibResult && (
          <p
            className={`text-xs ${
              calibResult.success ? "text-green-400" : "text-red-400"
            }`}
          >
            {calibResult.msg}
          </p>
        )}
      </div>

      {/* Save */}
      <button
        onClick={handleSave}
        className="w-full py-2 rounded bg-blue-600 hover:bg-blue-500 font-semibold"
      >
        {saved ? "Kaydedildi!" : "Kaydet"}
      </button>
    </div>
  );
}
