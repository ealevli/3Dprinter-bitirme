/**
 * CameraFeed — polls /camera/frame every 100ms instead of using MJPEG.
 * Each request is independent, so a slow frame never freezes the whole feed.
 */

import { useEffect, useRef, useState } from "react";

const POLL_MS = 100;       // ~10 fps
const ERROR_RETRY_MS = 2000;

export default function CameraFeed({ detectionImage, onClearDetection }) {
  const imgRef = useRef(null);
  const timerRef = useRef(null);
  const activeRef = useRef(true);
  const [error, setError] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    activeRef.current = true;

    async function fetchFrame() {
      if (!activeRef.current) return;

      try {
        const res = await fetch("/camera/frame", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const blob = await res.blob();
        if (!activeRef.current) return;

        const url = URL.createObjectURL(blob);

        if (imgRef.current) {
          const old = imgRef.current.src;
          imgRef.current.src = url;
          if (old && old.startsWith("blob:")) URL.revokeObjectURL(old);
        }

        setError(false);
        timerRef.current = setTimeout(fetchFrame, POLL_MS);
      } catch (err) {
        if (!activeRef.current) return;
        setError(true);
        setErrorMsg(err.message || "Bağlantı hatası");
        timerRef.current = setTimeout(fetchFrame, ERROR_RETRY_MS);
      }
    }

    fetchFrame();

    return () => {
      activeRef.current = false;
      clearTimeout(timerRef.current);
      if (imgRef.current?.src?.startsWith("blob:")) {
        URL.revokeObjectURL(imgRef.current.src);
      }
    };
  }, []);

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
      <img
        ref={imgRef}
        alt="Canlı Kamera"
        className="w-full h-full object-contain"
      />

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
