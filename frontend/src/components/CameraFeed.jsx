/**
 * CameraFeed — polls /camera/frame every 100ms instead of using MJPEG.
 * Each request is independent, so a slow frame never freezes the whole feed.
 */

import { useEffect, useRef, useState, useCallback } from "react";

const POLL_MS = 100; // ~10 fps — smooth enough, low CPU
const ERROR_RETRY_MS = 2000;

export default function CameraFeed({ detectionImage }) {
  const imgRef = useRef(null);
  const timerRef = useRef(null);
  const activeRef = useRef(true);
  const [error, setError] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const poll = useCallback(() => {
    if (!activeRef.current) return;
    const url = `/camera/frame?t=${Date.now()}`;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (!activeRef.current) return;
        const objectUrl = URL.createObjectURL(blob);
        if (imgRef.current) {
          const old = imgRef.current.src;
          imgRef.current.src = objectUrl;
          // Revoke the previous object URL to free memory
          if (old && old.startsWith("blob:")) URL.revokeObjectURL(old);
        }
        setError(false);
        timerRef.current = setTimeout(poll, POLL_MS);
      })
      .catch((err) => {
        if (!activeRef.current) return;
        setError(true);
        setErrorMsg(err.message);
        timerRef.current = setTimeout(poll, ERROR_RETRY_MS);
      });
  }, []);

  useEffect(() => {
    activeRef.current = true;
    setError(false);
    timerRef.current = setTimeout(poll, 50);
    return () => {
      activeRef.current = false;
      clearTimeout(timerRef.current);
      // Revoke current blob URL on unmount
      if (imgRef.current?.src?.startsWith("blob:")) {
        URL.revokeObjectURL(imgRef.current.src);
      }
    };
  }, [poll]);

  // Camera index changed from Settings → restart polling
  useEffect(() => {
    const handler = () => {
      clearTimeout(timerRef.current);
      setError(false);
      timerRef.current = setTimeout(poll, 300);
    };
    window.addEventListener("camera-index-changed", handler);
    return () => window.removeEventListener("camera-index-changed", handler);
  }, [poll]);

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
          onClick={() => {
            /* parent clears detectionImage — nothing to do here */
          }}
          className="absolute top-2 right-2 text-xs bg-black/50 hover:bg-black/80 text-white px-2 py-1 rounded"
        >
          Canlıya dön
        </button>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {/* Live feed */}
      <img
        ref={imgRef}
        alt="Canlı Kamera"
        className="w-full h-full object-contain"
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
