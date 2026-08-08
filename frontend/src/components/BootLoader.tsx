"use client";

import { useEffect, useMemo, useState } from "react";

const MIN_BOOT_MS = 1200;
const HEALTH_RETRY_MS = 900;
const HEALTH_TIMEOUT_MS = 20000;

function getApiBase(): string {
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  return process.env.NEXT_PUBLIC_API_URL || "/api";
}

async function waitForApiHealth(): Promise<void> {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  const base = getApiBase();
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${base}/health`, { cache: "no-store" });
      if (res.ok) return;
    } catch {
      // keep retrying until timeout
    }
    await new Promise((r) => setTimeout(r, HEALTH_RETRY_MS));
  }
}

class Line {
  x: number;
  y: number;
  endAngle: number;
  endSpeed: number;
  endDir: number;
  endChangeFreq: number;
  c1Angle: number;
  c1Speed: number;
  c1Dir: number;
  c1ChangeFreq: number;
  c2Angle: number;
  c2Speed: number;
  c2Dir: number;
  c2ChangeFreq: number;
  c1 = { x: 0, y: 0 };
  c2 = { x: 0, y: 0 };
  end = { x: 0, y: 0 };
  color = "rgba(199, 242, 208, .10)";
  width = 1;
  private readonly widthPx: number;
  private readonly heightPx: number;

  constructor(widthPx: number, heightPx: number) {
    this.widthPx = widthPx;
    this.heightPx = heightPx;
    this.x = widthPx / 2;
    this.y = heightPx / 2;

    this.endAngle = Math.floor(Math.random() * 360);
    this.endSpeed = (Math.floor(Math.random() * 10) + 1) / 50;
    this.endDir = Math.floor(Math.random() * 2) === 0 ? -1 : 1;
    this.endChangeFreq = Math.floor(Math.random() * 200) + 1;

    this.c1Angle = Math.floor(Math.random() * 360);
    this.c1Speed = (Math.floor(Math.random() * 10) + 1) / 20;
    this.c1Dir = Math.floor(Math.random() * 2) === 0 ? -1 : 1;
    this.c1ChangeFreq = Math.floor(Math.random() * 200) + 1;

    this.c2Angle = Math.floor(Math.random() * 360);
    this.c2Speed = (Math.floor(Math.random() * 10) + 1) / 20;
    this.c2Dir = Math.floor(Math.random() * 2) === 0 ? -1 : 1;
    this.c2ChangeFreq = Math.floor(Math.random() * 200) + 1;

    this.definePoints();
  }

  private aroundPoint(x: number, y: number, dist: number, ang: number) {
    const angle = (ang * Math.PI) / 180;
    return {
      x: x + Math.cos(angle) * dist,
      y: y + Math.sin(angle) * dist,
    };
  }

  private definePoints() {
    this.c1 = this.aroundPoint(this.x, this.y, 100, this.c1Angle);
    this.end = this.aroundPoint(this.x, this.y, 150, this.endAngle);
    this.c2 = this.aroundPoint(this.end.x, this.end.y, 100, this.c2Angle);
  }

  moveAndDraw(ctx: CanvasRenderingContext2D) {
    this.endChangeFreq -= 1;
    if (this.endChangeFreq === 0) {
      this.endDir *= -1;
      this.endChangeFreq = Math.floor(Math.random() * 200) + 1;
    }

    this.c1ChangeFreq -= 1;
    if (this.c1ChangeFreq === 0) {
      this.c1Dir *= -1;
      this.c1ChangeFreq = Math.floor(Math.random() * 200) + 1;
    }

    this.c2ChangeFreq -= 1;
    if (this.c2ChangeFreq === 0) {
      this.c2Dir *= -1;
      this.c2ChangeFreq = Math.floor(Math.random() * 200) + 1;
    }

    this.c1Angle += this.c1Dir * this.c1Speed;
    this.c2Angle += this.c2Dir * this.c2Speed;
    this.endAngle += this.endDir * this.endSpeed;
    this.definePoints();

    ctx.beginPath();
    ctx.moveTo(this.x, this.y);
    ctx.bezierCurveTo(this.c1.x, this.c1.y, this.c2.x, this.c2.y, this.end.x, this.end.y);
    ctx.strokeStyle = this.color;
    ctx.lineWidth = this.width;
    ctx.lineCap = "round";
    ctx.stroke();
    ctx.closePath();
  }
}

export function BootLoader() {
  const [done, setDone] = useState(false);
  const totalTentacles = useMemo(() => 200, []);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      const started = Date.now();
      document.body.classList.add("boot-loading");

      await Promise.all([
        waitForApiHealth().catch(() => undefined),
        document.readyState === "complete"
          ? Promise.resolve()
          : new Promise<void>((resolve) => {
              const onLoad = () => {
                window.removeEventListener("load", onLoad);
                resolve();
              };
              window.addEventListener("load", onLoad);
            }),
      ]);

      const elapsed = Date.now() - started;
      if (elapsed < MIN_BOOT_MS) {
        await new Promise((r) => setTimeout(r, MIN_BOOT_MS - elapsed));
      }

      if (!cancelled) {
        setDone(true);
        document.body.classList.remove("boot-loading");
      }
    };

    run();

    return () => {
      cancelled = true;
      document.body.classList.remove("boot-loading");
    };
  }, []);

  useEffect(() => {
    const canvas = document.getElementById("canvas") as HTMLCanvasElement | null;
    if (!canvas || done) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = document.documentElement.clientWidth;
    let height = document.documentElement.clientHeight;
    canvas.width = width;
    canvas.height = height;

    let lines: Line[] = [];
    let frame = 0;

    const init = () => {
      lines = [];
      ctx.shadowColor = "rgba(199, 242, 208, 0.85)";
      ctx.shadowBlur = 10;
      for (let i = 0; i < totalTentacles; i += 1) {
        lines.push(new Line(width, height));
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, width, height);
      for (const line of lines) {
        line.moveAndDraw(ctx);
      }
      frame = requestAnimationFrame(animate);
    };

    const onResize = () => {
      width = document.documentElement.clientWidth;
      height = document.documentElement.clientHeight;
      canvas.width = width;
      canvas.height = height;
      init();
    };

    init();
    animate();
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
    };
  }, [done, totalTentacles]);

  if (done) return null;

  return (
    <div className="opa boot-loader" aria-live="polite" aria-label="Loading Job OS">
      <canvas id="canvas" />
      <div className="boot-loader-text">Booting Job OS</div>
    </div>
  );
}
