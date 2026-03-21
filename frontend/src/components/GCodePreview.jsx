/**
 * GCodePreview — Cura-style canvas preview.
 *
 * Shows:
 *   - Green dashed line  : part contour (from detection)
 *   - Cyan line          : WALL-OUTER perimeter pass
 *   - Blue lines         : infill (zigzag / spiral / parallel)
 *
 * Aspect ratio is always preserved (no stretching).
 */

import { useEffect, useRef } from "react";

export default function GCodePreview({
  paths     = [],   // infill XY points  [{x,y}]
  wallPaths = [],   // wall XY points    [{x,y}]
  contourMm = [],   // raw detection contour [[x,y]]
}) {
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

    const hasData = paths.length > 0 || wallPaths.length > 0 || contourMm.length > 0;
    if (!hasData) return;

    // ── Compute unified bounding box ─────────────────────────────────────
    const allX = [];
    const allY = [];
    paths.forEach(p    => { allX.push(p.x); allY.push(p.y); });
    wallPaths.forEach(p => { allX.push(p.x); allY.push(p.y); });
    contourMm.forEach(([x, y]) => { allX.push(x); allY.push(y); });

    if (allX.length === 0) return;

    const minX = Math.min(...allX);
    const maxX = Math.max(...allX);
    const minY = Math.min(...allY);
    const maxY = Math.max(...allY);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;

    // Uniform scale — keep aspect ratio
    const pad    = 28;
    const scaleX = (W - 2 * pad) / rangeX;
    const scaleY = (H - 2 * pad) / rangeY;
    const scale  = Math.min(scaleX, scaleY);

    const drawW = rangeX * scale;
    const drawH = rangeY * scale;
    const offX  = pad + (W - 2 * pad - drawW) / 2;
    const offY  = pad + (H - 2 * pad - drawH) / 2;

    /** Printer mm → canvas px  (Y-flipped: printer Y up, canvas Y down) */
    const tc = (x, y) => ({
      cx: offX + (x - minX) * scale,
      cy: offY + drawH - (y - minY) * scale,
    });

    // ── Helper: stroke an array of {x,y} as a polyline ───────────────────
    const strokeLine = (pts, color, width = 1, dash = []) => {
      if (pts.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth   = width;
      ctx.setLineDash(dash);
      ctx.beginPath();
      pts.forEach((p, i) => {
        const { cx, cy } = tc(p.x, p.y);
        i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    };

    // ── 1. Part contour outline (green dashed) ────────────────────────────
    if (contourMm.length >= 3) {
      const pts = contourMm.map(([x, y]) => ({ x, y }));
      strokeLine([...pts, pts[0]], "#22c55e", 1.5, [5, 4]);
    }

    // ── 2. Wall-outer path (cyan) ─────────────────────────────────────────
    if (wallPaths.length >= 2) {
      strokeLine(wallPaths, "#06b6d4", 1.5);
    }

    // ── 3. Infill — paths = [start, end, start, end, ...] pairs ──────────
    // Every 2 consecutive points form one coating line segment.
    // Draw them all as individual lines (no jump-detection complexity).
    if (paths.length >= 2) {
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth   = 1.5;
      ctx.setLineDash([]);

      // paths arrive as flat list: [travelPt, coatEndPt, travelPt, coatEndPt…]
      // Just draw every consecutive pair as a line segment.
      for (let i = 0; i + 1 < paths.length; i += 2) {
        const { cx: x1, cy: y1 } = tc(paths[i].x,   paths[i].y);
        const { cx: x2, cy: y2 } = tc(paths[i+1].x, paths[i+1].y);
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
    }

    // ── 4. Axis labels ────────────────────────────────────────────────────
    ctx.fillStyle = "#475569";
    ctx.font      = "10px monospace";
    ctx.fillText(`X ${minX.toFixed(1)}`, offX, H - 6);
    ctx.fillText(`${maxX.toFixed(1)} mm`, offX + drawW - 34, H - 6);
    ctx.fillText(`${maxY.toFixed(1)}`, 4, offY + 8);
    ctx.fillText(`${minY.toFixed(1)} mm`, 4, offY + drawH);

    // ── 5. Legend ────────────────────────────────────────────────────────
    const legend = [
      { color: "#22c55e", label: "Kontur" },
      { color: "#06b6d4", label: "Dış çevre" },
      { color: "#3b82f6", label: "Dolgu" },
    ];
    legend.forEach(({ color, label }, i) => {
      const lx = W - 80;
      const ly = 12 + i * 16;
      ctx.strokeStyle = color;
      ctx.lineWidth   = 2;
      ctx.beginPath();
      ctx.moveTo(lx, ly);
      ctx.lineTo(lx + 14, ly);
      ctx.stroke();
      ctx.fillStyle = "#94a3b8";
      ctx.font      = "9px sans-serif";
      ctx.fillText(label, lx + 18, ly + 4);
    });

  }, [paths, wallPaths, contourMm]);

  if (paths.length === 0 && wallPaths.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-slate-500 text-sm">
        G-code önizleme için "Önizle" butonuna basın.
      </div>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      width={620}
      height={240}
      className="w-full h-full"
    />
  );
}
