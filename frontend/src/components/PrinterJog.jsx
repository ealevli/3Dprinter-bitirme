import { useState } from "react";
import axios from "axios";

const STEPS = [0.1, 1, 5, 10];
const FEED = { XY: 3000, Z: 300 };

export default function PrinterJog({ onLog }) {
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [rawCmd, setRawCmd] = useState("");

  async function move(axis, sign) {
    if (busy) return;
    setBusy(true);
    const distance = sign * step;
    const feed = axis === "Z" ? FEED.Z : FEED.XY;
    try {
      await axios.post("/jog/move", { axis, distance, feed_rate: feed });
      onLog?.(`Jog: ${axis}${distance > 0 ? "+" : ""}${distance} mm`);
    } catch (e) {
      onLog?.(`Jog hatası: ${e.response?.data?.detail ?? e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function home(axes) {
    if (busy) return;
    setBusy(true);
    onLog?.(`Home: ${axes.join(" ")} bekleniyor…`);
    try {
      const res = await axios.post("/jog/home", { axes });
      onLog?.(res.data.message);
    } catch (e) {
      onLog?.(`Home hatası: ${e.response?.data?.detail ?? e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function sendRaw() {
    if (!rawCmd.trim() || busy) return;
    setBusy(true);
    try {
      const res = await axios.post("/jog/send", { command: rawCmd.trim() });
      onLog?.(res.data.message);
      setRawCmd("");
    } catch (e) {
      onLog?.(`Komut hatası: ${e.response?.data?.detail ?? e.message}`);
    } finally {
      setBusy(false);
    }
  }

  const btn =
    "flex items-center justify-center rounded font-bold text-lg select-none transition-colors " +
    (busy
      ? "bg-slate-700 text-slate-500 cursor-not-allowed"
      : "bg-slate-600 hover:bg-slate-500 active:bg-slate-400 text-white cursor-pointer");

  return (
    <div className="bg-slate-800 rounded-lg p-3 space-y-3 text-sm">
      <h2 className="font-semibold text-slate-300 text-xs uppercase tracking-wide">
        Manuel Kontrol
      </h2>

      {/* Step size */}
      <div className="flex gap-1">
        {STEPS.map((s) => (
          <button
            key={s}
            onClick={() => setStep(s)}
            className={`flex-1 py-1 rounded text-xs font-semibold transition-colors ${
              step === s
                ? "bg-blue-600 text-white"
                : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            }`}
          >
            {s} mm
          </button>
        ))}
      </div>

      <div className="flex gap-3">
        {/* XY pad */}
        <div className="flex-1">
          <p className="text-xs text-slate-500 mb-1 text-center">X / Y</p>
          <div className="grid grid-cols-3 gap-1" style={{ gridTemplateRows: "repeat(3,2rem)" }}>
            {/* Row 1 */}
            <div />
            <button className={btn} onClick={() => move("Y", +1)} title="Y+">▲</button>
            <div />
            {/* Row 2 */}
            <button className={btn} onClick={() => move("X", -1)} title="X-">◄</button>
            {/* Center: home XY */}
            <button
              className={`${btn} text-sm`}
              onClick={() => home(["X", "Y"])}
              title="XY Home"
            >
              ⌂
            </button>
            <button className={btn} onClick={() => move("X", +1)} title="X+">►</button>
            {/* Row 3 */}
            <div />
            <button className={btn} onClick={() => move("Y", -1)} title="Y-">▼</button>
            <div />
          </div>
        </div>

        {/* Z pad */}
        <div className="w-16">
          <p className="text-xs text-slate-500 mb-1 text-center">Z</p>
          <div className="flex flex-col gap-1">
            <button className={`${btn} h-8`} onClick={() => move("Z", +1)} title="Z+">▲</button>
            <button
              className={`${btn} h-8 text-sm`}
              onClick={() => home(["Z"])}
              title="Z Home"
            >
              ⌂
            </button>
            <button className={`${btn} h-8`} onClick={() => move("Z", -1)} title="Z-">▼</button>
          </div>
        </div>
      </div>

      {/* Home all */}
      <button
        onClick={() => home(["X", "Y", "Z"])}
        disabled={busy}
        className="w-full py-1.5 rounded bg-amber-700 hover:bg-amber-600 disabled:opacity-40 text-xs font-semibold"
      >
        ⌂ Tümünü Home'la (G28)
      </button>

      {/* Raw G-code input */}
      <div className="flex gap-1">
        <input
          value={rawCmd}
          onChange={(e) => setRawCmd(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendRaw()}
          placeholder="G-code gönder (örn: M114)"
          className="flex-1 bg-slate-700 rounded px-2 py-1 text-xs font-mono placeholder-slate-500 focus:outline-none"
        />
        <button
          onClick={sendRaw}
          disabled={busy || !rawCmd.trim()}
          className="px-3 py-1 rounded bg-slate-600 hover:bg-slate-500 disabled:opacity-40 text-xs font-semibold"
        >
          Gönder
        </button>
      </div>
    </div>
  );
}
