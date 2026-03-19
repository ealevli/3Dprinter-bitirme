/**
 * CameraFeed — displays the live MJPEG stream from the backend.
 * When a detection image (base64 annotated frame) is passed, it overlays that instead.
 */

import { useState } from "react";

export default function CameraFeed({ detectionImage }) {
  const [streamError, setStreamError] = useState(false);

  // If we have an annotated detection image, show it temporarily.
  if (detectionImage) {
    return (
      <img
        src={`data:image/jpeg;base64,${detectionImage}`}
        alt="Tespit"
        className="w-full h-full object-contain"
      />
    );
  }

  if (streamError) {
    return (
      <div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">
        Kamera bağlanamadı. Ayarlar sayfasından port kontrol edin.
      </div>
    );
  }

  return (
    <img
      src="/camera/stream"
      alt="Canlı Kamera"
      className="w-full h-full object-contain"
      onError={() => setStreamError(true)}
    />
  );
}
