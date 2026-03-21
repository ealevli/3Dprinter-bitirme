/**
 * CameraFeed — displays the live MJPEG stream from the backend.
 * Auto-reconnects when the stream drops. Shows annotated detection image when provided.
 */

import { useState, useEffect, useRef, useCallback } from "react";

export default function CameraFeed({ detectionImage }) {
  const [streamKey, setStreamKey] = useState(Date.now());
  const [status, setStatus] = useState("connecting"); // connecting | ok | error
  const retryRef = useRef(null);

  // Build URL with timestamp so each reconnect is a fresh request
  const streamUrl = `/camera/stream?t=${streamKey}`;

  const reconnect = useCallback(() => {
    setStatus("connecting");
    setStreamKey(Date.now());
  }, []);

  // If stream errors, wait 3s and auto-retry.
  useEffect(() => {
    if (status === "error") {
      retryRef.current = setTimeout(reconnect, 3000);
    }
    return () => clearTimeout(retryRef.current);
  }, [status, reconnect]);

  // Listen for camera index changes from Settings page.
  useEffect(() => {
    const handler = () => reconnect();
    window.addEventListener("camera-index-changed", handler);
    return () => window.removeEventListener("camera-index-changed", handler);
  }, [reconnect]);

  // If we have an annotated detection image, overlay it.
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

  return (
    <div className="relative w-full h-full">
      {/* Stream image */}
      <img
        key={streamKey}
        src={streamUrl}
        alt="Canlı Kamera"
        className={`w-full h-full object-contain transition-opacity ${
          status === "ok" ? "opacity-100" : "opacity-0"
        }`}
        onLoad={() => setStatus("ok")}
        onError={() => setStatus("error")}
      />

      {/* Overlay: connecting */}
      {status === "connecting" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 text-sm gap-2">
          <div className="w-6 h-6 border-2 border-slate-500 border-t-blue-400 rounded-full animate-spin" />
          <span>Kamera bağlanıyor…</span>
        </div>
      )}

      {/* Overlay: error */}
      {status === "error" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 text-sm gap-3">
          <span className="text-2xl">📷</span>
          <span>Kamera bağlantısı kesildi</span>
          <span className="text-xs text-slate-500">3 saniyede yeniden deniyor…</span>
          <button
            onClick={reconnect}
            className="mt-1 text-xs bg-slate-700 hover:bg-slate-600 text-white px-3 py-1 rounded"
          >
            Hemen Yenile
          </button>
          <span className="text-xs text-slate-600 mt-1">
            Sorun devam ederse Ayarlar → Kamera İndeksi kontrol et
          </span>
        </div>
      )}

      {/* Manual refresh button (top-right, visible when ok) */}
      {status === "ok" && (
        <button
          onClick={reconnect}
          title="Kamera stream'ini yenile"
          className="absolute top-2 right-2 text-xs bg-black/40 hover:bg-black/70 text-white px-2 py-0.5 rounded opacity-0 hover:opacity-100 transition-opacity"
        >
          ↺
        </button>
      )}
    </div>
  );
}
