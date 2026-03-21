/**
 * CameraFeed — displays the live MJPEG stream from the backend.
 * Auto-reconnects on error. Shows annotated detection image when provided.
 */

import { useState, useEffect, useRef, useCallback } from "react";

export default function CameraFeed({ detectionImage }) {
  const [streamKey, setStreamKey] = useState(Date.now());
  const [hasError, setHasError] = useState(false);
  const retryRef = useRef(null);

  const reconnect = useCallback(() => {
    setHasError(false);
    setStreamKey(Date.now());
  }, []);

  // Auto-retry 3s after error
  useEffect(() => {
    if (hasError) {
      retryRef.current = setTimeout(reconnect, 3000);
    }
    return () => clearTimeout(retryRef.current);
  }, [hasError, reconnect]);

  // Listen for camera index change from Settings
  useEffect(() => {
    const handler = () => reconnect();
    window.addEventListener("camera-index-changed", handler);
    return () => window.removeEventListener("camera-index-changed", handler);
  }, [reconnect]);

  // Show annotated detection image
  if (detectionImage) {
    return (
      <div className="relative w-full h-full">
        <img
          src={`data:image/jpeg;base64,${detectionImage}`}
          alt="Tespit"
          className="w-full h-full object-contain"
        />
        <button
          onClick={reconnect}
          className="absolute top-2 right-2 text-xs bg-black/50 hover:bg-black/80 text-white px-2 py-1 rounded"
        >
          Canlıya dön
        </button>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 text-sm gap-3">
        <span className="text-3xl">📷</span>
        <span>Kamera bağlantısı kesildi</span>
        <span className="text-xs text-slate-500">3 saniyede yeniden deniyor…</span>
        <button
          onClick={reconnect}
          className="text-xs bg-slate-700 hover:bg-slate-600 text-white px-3 py-1.5 rounded"
        >
          Hemen Yenile
        </button>
        <span className="text-xs text-slate-600">
          Sorun devam ederse Ayarlar → Kamera İndeksi kontrol et
        </span>
      </div>
    );
  }

  // Just show the stream — no opacity trick, no connecting overlay.
  // onError fires if the backend returns non-2xx or connection drops.
  return (
    <img
      key={streamKey}
      src={`/camera/stream?t=${streamKey}`}
      alt="Canlı Kamera"
      className="w-full h-full object-contain"
      onError={() => setHasError(true)}
    />
  );
}
