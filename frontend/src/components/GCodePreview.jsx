/**
 * GCodePreview — renders G-code XY paths on a canvas.
 * Preserves aspect ratio so the shape looks correct (no stretching).
 * `paths` is an array of {x, y} objects in printer mm coordinates.
 */

import { useEffect, useRef } from "react";

export default function GCodePreview({ paths = [], contourMm = [] }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, W, H);

    if (paths.length === 0) return;

    const pad = 24;

    // ── Compute bounds from paths + contour ──────────────────────────────
    const allX = paths.map((p) => p.x);
    const allY = paths.map((p) => p.y);
    if (contourMm.length) {
      contourMm.forEach(([x, y]) => { allX.push(x); allY.push(y); });
    }
    const minX = Math.min(...allX);
    const maxX = Math.max(...allX);
    const minY = Math.min(...allY);
    const maxY = Math.max(...allY);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    // ── Preserve aspect ratio ─────────────────────────────────────────────
    const scaleX = (W - 2 * pad) / rangeX;
    const scaleY = (H - 2 * pad) / rangeY;
    const scale  = Math.min(scaleX, scaleY);  // uniform scale

    // Centre in canvas
    const drawW = rangeX * scale;
    const drawH = rangeY * scale;
    const offX  = pad + (W - 2 * pad - drawW) / 2;
    const offY  = pad + (H - 2 * pad - drawH) / 2;

    const toCanvas = (x, y) => ({
      cx: offX + (x - minX) * scale,
      cy: offY + drawH - (y - minY) * scale,   // flip Y (printer Y = up)
    });

    // ── Draw part contour outline ─────────────────────────────────────────
    if (contourMm.length >= 3) {
      ctx.strokeStyle = "#22c55e";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      contourMm.forEach(([x, y], i) => {
        const { cx, cy } = toCanvas(x, y);
        if (i === 0) ctx.moveTo(cx, cy);
        else ctx.lineTo(cx, cy);
      });
      ctx.closePath();
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // ── Draw tool path ────────────────────────────────────────────────────
    // Detect "travel" vs "coating" moves: large jumps in position = travel
    ctx.lineWidth = 1;
    let prevPt = null;
    let inTravel = true;

    paths.forEach((p) => {
      const { cx, cy } = toCanvas(p.x, p.y);

      if (!prevPt) {
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        prevPt = { cx, cy };
        inTravel = true;
        return;
      }

      const dx = Math.abs(cx - prevPt.cx);
      const dy = Math.abs(cy - prevPt.cy);
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Large jump = travel move (dim/dashed), small = coating (bright)
      if (dist > 20) {
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        inTravel = true;
      } else {
        if (inTravel) {
          ctx.stroke();
          ctx.strokeStyle = "#3b82f6";
          ctx.beginPath();
          ctx.moveTo(prevPt.cx, prevPt.cy);
          inTravel = false;
        }
        ctx.lineTo(cx, cy);
      }

      prevPt = { cx, cy };
    });
    ctx.stroke();

    // ── Axis labels ──────────────────────────────────────────────────────
    ctx.fillStyle = "#475569";
    ctx.font = "10px monospace";
    ctx.fillText(`${minX.toFixed(0)}`, offX, H - 4);
    ctx.fillText(`${maxX.toFixed(0)} mm`, offX + drawW - 24, H - 4);
    ctx.fillText(`${minY.toFixed(0)}`, 2, offY + drawH);
    ctx.fillText(`${maxY.toFixed(0)}`, 2, offY + 8);
  }, [paths, contourMm]);

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
      height={220}
      className="w-full h-full"
    />
  );
}
