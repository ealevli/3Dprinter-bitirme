/**
 * GCodePreview — Cura-style canvas preview with full bed view.
 *
 * Always shows the 235x235 mm printer bed so the user can see where
 * the detected part sits on the bed and where the BLTouch will probe.
 *
 * Layers (bottom to top):
 *   1. Bed background (dark gray fill)
 *   2. Grid lines at 50 mm intervals (very subtle)
 *   3. Center crosshair at (117.5, 117.5) — BLTouch probe point
 *   4. Part contour (green dashed)
 *   5. WALL-OUTER perimeter (cyan)
 *   6. Infill segments (blue)
 *   7. Axis labels + legend
 *
 * Props:
 *   paths     : list of segments [[{x,y},...], ...] — infill coating passes
 *   wallPaths : flat list [{x,y}] — perimeter polyline
 *   contourMm : raw detection contour [[x,y]]
 *   bedW      : bed width in mm  (default 235)
 *   bedH      : bed height in mm (default 235)
 */

import { useEffect, useRef } from "react";

const BED_W_DEFAULT = 235;
const BED_H_DEFAULT = 235;

export default function GCodePreview({
  paths     = [],
  wallPaths = [],
  contourMm = [],
  bedW      = BED_W_DEFAULT,
  bedH      = BED_H_DEFAULT,
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

    // ── Coordinate transform: printer mm → canvas px ──────────────────
    // Fixed to full bed — no zoom-to-fit, so part position is always correct.
    const pad    = 30;
    const scaleX = (W - 2 * pad) / bedW;
    const scaleY = (H - 2 * pad) / bedH;
    const scale  = Math.min(scaleX, scaleY);

    const drawW = bedW * scale;
    const drawH = bedH * scale;
    const offX  = pad + (W - 2 * pad - drawW) / 2;
    const offY  = pad + (H - 2 * pad - drawH) / 2;

    // Y-flip: printer Y increases upward, canvas Y increases downward
    const tc = (x, y) => ({
      cx: offX + x * scale,
      cy: offY + drawH - y * scale,
    });

    // ── 1. Bed fill ────────────────────────────────────────────────────
    ctx.fillStyle = "#1e293b";
    const bedTL = tc(0, bedH);
    ctx.fillRect(bedTL.cx, bedTL.cy, drawW, drawH);

    // ── 2. Subtle grid lines every 50 mm ──────────────────────────────
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 0.5;
    ctx.setLineDash([2, 4]);
    for (let mm = 0; mm <= bedW; mm += 50) {
      const { cx: gx1, cy: gy1 } = tc(mm, 0);
      const { cx: gx2, cy: gy2 } = tc(mm, bedH);
      ctx.beginPath(); ctx.moveTo(gx1, gy1); ctx.lineTo(gx2, gy2); ctx.stroke();
    }
    for (let mm = 0; mm <= bedH; mm += 50) {
      const { cx: gx1, cy: gy1 } = tc(0, mm);
      const { cx: gx2, cy: gy2 } = tc(bedW, mm);
      ctx.beginPath(); ctx.moveTo(gx1, gy1); ctx.lineTo(gx2, gy2); ctx.stroke();
    }
    ctx.setLineDash([]);

    // ── 3. Bed boundary ───────────────────────────────────────────────
    ctx.strokeStyle = "#475569";
    ctx.lineWidth = 1.5;
    const bl = tc(0, 0), br = tc(bedW, 0), tr2 = tc(bedW, bedH), tl = tc(0, bedH);
    ctx.beginPath();
    ctx.moveTo(tl.cx, tl.cy);
    ctx.lineTo(tr2.cx, tr2.cy);
    ctx.lineTo(br.cx, br.cy);
    ctx.lineTo(bl.cx, bl.cy);
    ctx.closePath();
    ctx.stroke();

    // ── 4. Center crosshair + BLTouch probe point ─────────────────────
    const { cx: ccx, cy: ccy } = tc(bedW / 2, bedH / 2);
    const arm = 18;

    // Crosshair lines
    ctx.strokeStyle = "#f97316";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(ccx - arm, ccy); ctx.lineTo(ccx + arm, ccy);
    ctx.moveTo(ccx, ccy - arm); ctx.lineTo(ccx, ccy + arm);
    ctx.stroke();

    // Center dot
    ctx.fillStyle = "#f97316";
    ctx.beginPath();
    ctx.arc(ccx, ccy, 3.5, 0, Math.PI * 2);
    ctx.fill();

    // Label
    ctx.fillStyle = "#fb923c";
    ctx.font = "9px monospace";
    ctx.fillText("BLTouch", ccx + 6, ccy - 5);
    ctx.fillText(`(${bedW / 2}, ${bedH / 2})`, ccx + 6, ccy + 7);

    // ── Helper: stroke a flat {x,y} array as polyline ─────────────────
    const strokePolyline = (pts, color, width = 1.5, dash = []) => {
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

    // ── 5. Part contour (green dashed) ────────────────────────────────
    if (contourMm.length >= 3) {
      const pts = contourMm.map(([x, y]) => ({ x, y }));
      strokePolyline([...pts, pts[0]], "#22c55e", 1.5, [5, 4]);
    }

    // ── 6. Wall-outer (cyan) ──────────────────────────────────────────
    if (wallPaths.length >= 2) {
      strokePolyline(wallPaths, "#06b6d4", 1.5);
    }

    // ── 7. Infill segments (blue) ─────────────────────────────────────
    if (paths.length > 0) {
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth   = 1.5;
      ctx.setLineDash([]);
      paths.forEach(seg => {
        if (seg.length < 2) return;
        ctx.beginPath();
        seg.forEach((p, i) => {
          const { cx, cy } = tc(p.x, p.y);
          i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
        });
        ctx.stroke();
      });
    }

    // ── 8. Corner labels ──────────────────────────────────────────────
    ctx.fillStyle = "#475569";
    ctx.font = "9px monospace";
    const lbl = tc(0, 0);
    ctx.fillText("0,0", lbl.cx + 2, lbl.cy - 3);
    const rbr = tc(bedW, 0);
    ctx.fillText(`${bedW},0`, rbr.cx - 28, rbr.cy - 3);

    // ── 9. Legend ─────────────────────────────────────────────────────
    const legend = [
      { color: "#f97316", label: "BLTouch merkezi" },
      { color: "#22c55e", label: "Kontur" },
      { color: "#06b6d4", label: "Dış çevre" },
      { color: "#3b82f6", label: "Dolgu" },
    ];
    legend.forEach(({ color, label }, i) => {
      const lx = W - 90;
      const ly = 12 + i * 16;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(lx, ly);
      ctx.lineTo(lx + 14, ly);
      ctx.stroke();
      ctx.fillStyle = "#94a3b8";
      ctx.font = "9px sans-serif";
      ctx.fillText(label, lx + 18, ly + 4);
    });

  }, [paths, wallPaths, contourMm, bedW, bedH]);

  return (
    <canvas
      ref={canvasRef}
      width={620}
      height={300}
      className="w-full h-full"
    />
  );
}
