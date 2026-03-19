/**
 * GCodePreview — renders G-code XY paths on a canvas.
 * `paths` is an array of {x, y} objects in printer mm coordinates.
 */

import { useEffect, useRef } from "react";

export default function GCodePreview({ paths = [] }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || paths.length === 0) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, W, H);

    // Compute bounds.
    const xs = paths.map((p) => p.x);
    const ys = paths.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const pad = 20;

    const toCanvas = (x, y) => ({
      cx: pad + ((x - minX) / rangeX) * (W - 2 * pad),
      cy: H - pad - ((y - minY) / rangeY) * (H - 2 * pad),
    });

    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 1;
    ctx.beginPath();
    paths.forEach((p, i) => {
      const { cx, cy } = toCanvas(p.x, p.y);
      if (i === 0) ctx.moveTo(cx, cy);
      else ctx.lineTo(cx, cy);
    });
    ctx.stroke();
  }, [paths]);

  if (paths.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">
        G-code önizleme için "Önizle" butonuna basın.
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      width={600}
      height={200}
      className="w-full h-full"
    />
  );
}
