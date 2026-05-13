/**
 * CameraFeed — polls /camera/frame every 100ms instead of using MJPEG.
 * Each request is independent, so a slow frame never freezes the whole feed.
 */

import { useEffect, useRef, useState, useCallback } from "react";

const POLL_MS = 100; // ~10 fps — smooth enough, low CPU
const ERROR_RETRY_MS = 2000;

export default function CameraFeed({ detectionImage, onClearDetection }) {
  const imgRef = useRef(null);
  const timerRef = useRef(null);
  const activeRef = useRef(true);
  const [error, setError] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // When camera index changes, add a timestamp to force reload the image stream
  const [streamUrl, setStreamUrl] = useState("/camera/stream");

  useEffect(() => {
    const handler = () => {
      setStreamUrl(`/camera/stream?t=${Date.now()}`);
    };
    window.addEventListener("camera-index-changed", handler);
    return () => window.removeEventListener("camera-index-changed", handler);
  }, []);

  // Show annotated detection image overlay
  if (detectionImage) {
    return (
      <div className="relative w-full h-full">
        <img
          src={`data:image/jpeg;base64,${detectionImage}`}
          alt="Tespit"
          className="w-full h-full object-contain"
        />
        <button
          onClick={onClearDetection}
          className="absolute top-2 right-2 text-xs bg-black/50 hover:bg-black/80 text-white px-2 py-1 rounded"
        >
          ▶ Canlıya dön
        </button>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Live MJPEG stream */}
      <img
        src={streamUrl}
        alt="Canlı Kamera"
        className="w-full h-full object-contain"
        onError={() => {
          setError(true);
          setErrorMsg("Yayın alınamadı");
        }}
        onLoad={() => setError(false)}
      />

      {/* Error overlay */}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900/80 text-slate-300 text-sm gap-2">
          <span className="text-2xl">📷</span>
          <span>Kamera bağlanamadı</span>
          <span className="text-xs text-slate-500">{errorMsg} — yeniden deneniyor…</span>
          <span className="text-xs text-slate-600">Ayarlar → Kamera İndeksi kontrol et</span>
        </div>
      )}
    </div>
  );
}
