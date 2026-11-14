// Scroll-driven motion for the public pages. Both effects switch off under
// prefers-reduced-motion and when IntersectionObserver is missing.
import { useEffect, useState, type RefObject } from "react";

function motionOff(): boolean {
  return (
    typeof IntersectionObserver === "undefined" ||
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Focus pull: every `.fx` element inside `root` goes from blurred, faded and
 * slightly small to sharp as it scrolls into view, like a camera racking focus.
 */
export function useFocusPull(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = root.current;
    if (!el || motionOff()) return;
    const targets = [...el.querySelectorAll<HTMLElement>(".fx")];
    const thresholds = Array.from({ length: 51 }, (_, i) => i / 50);
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const need =
            Math.min(window.innerHeight * 0.4, e.boundingClientRect.height * 0.7) || 1;
          const f = Math.min(1, Math.max(0, e.intersectionRect.height / need));
          const s = (e.target as HTMLElement).style;
          s.filter = f >= 1 ? "none" : `blur(${((1 - f) * 12).toFixed(1)}px)`;
          s.opacity = String(0.3 + 0.7 * f);
          s.transform = f >= 1 ? "none" : `scale(${(0.95 + 0.05 * f).toFixed(3)})`;
        }
      },
      { threshold: thresholds }
    );
    targets.forEach((t) => io.observe(t));
    return () => {
      io.disconnect();
      for (const t of targets) t.style.filter = t.style.opacity = t.style.transform = "";
    };
  }, [root]);
}

/**
 * Eased progress (0 to 1, ease-out cubic) that starts the first time `ref` is
 * 35% visible. Returns 1 straight away when motion is off.
 */
export function useCountUp(ref: RefObject<HTMLElement | null>, ms = 1300): number {
  const [off] = useState(motionOff);
  const [p, setP] = useState(off ? 1 : 0);
  useEffect(() => {
    const el = ref.current;
    if (off || !el) return;
    let raf = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        const t0 = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - t0) / ms);
          setP(1 - Math.pow(1 - t, 3));
          if (t < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      },
      { threshold: 0.35 }
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [ref, ms, off]);
  return p;
}
