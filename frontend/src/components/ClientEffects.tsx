"use client";

import { useEffect, useRef } from "react";

export function ClientEffects() {
  const cursorRef = useRef<HTMLDivElement>(null);
  const cursorRingRef = useRef<HTMLDivElement>(null);
  const sporeCanvasRef = useRef<HTMLCanvasElement>(null);
  const fogCanvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // --- CURSOR LOGIC ---
    const cursor = cursorRef.current;
    const cursorRing = cursorRingRef.current;
    let mx = -100;
    let my = -100;
    let rx = -100;
    let ry = -100;

    const onMouseMove = (e: MouseEvent) => {
      mx = e.clientX;
      my = e.clientY;
      if (cursor) {
        cursor.style.left = `${mx}px`;
        cursor.style.top = `${my}px`;
        cursor.style.opacity = "1";
      }
      if (cursorRing) {
        cursorRing.style.opacity = "1";
      }
    };

    const onMouseLeave = () => {
      if (cursor) cursor.style.opacity = "0";
      if (cursorRing) cursorRing.style.opacity = "0";
    };

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseleave", onMouseLeave);

    let ringFrameId = 0;
    const trackRing = () => {
      rx += (mx - rx) * 0.12;
      ry += (my - ry) * 0.12;
      if (cursorRing) {
        cursorRing.style.left = `${rx}px`;
        cursorRing.style.top = `${ry}px`;
      }
      ringFrameId = requestAnimationFrame(trackRing);
    };
    trackRing();

    // Event delegation for hover states
    const onMouseOver = (e: MouseEvent) => {
      const target = (e.target as HTMLElement).closest("a, button, select, input, label");
      if (target && cursor && cursorRing) {
        cursor.style.transform = "translate(-50%,-50%) scale(1.8)";
        cursorRing.style.transform = "translate(-50%,-50%) scale(1.5)";
        cursorRing.style.borderColor = "rgba(199, 242, 208, 0.5)";
        cursorRing.style.backgroundColor = "rgba(199, 242, 208, 0.05)";
      }
    };

    const onMouseOut = (e: MouseEvent) => {
      const target = (e.target as HTMLElement).closest("a, button, select, input, label");
      if (target && cursor && cursorRing) {
        cursor.style.transform = "translate(-50%,-50%) scale(1)";
        cursorRing.style.transform = "translate(-50%,-50%) scale(1)";
        cursorRing.style.borderColor = "rgba(199, 242, 208, 0.3)";
        cursorRing.style.backgroundColor = "transparent";
      }
    };

    document.addEventListener("mouseover", onMouseOver);
    document.addEventListener("mouseout", onMouseOut);


    // --- SPORE PARTICLES LOGIC ---
    const sporeCanvas = sporeCanvasRef.current;
    if (!sporeCanvas) return;
    const sCtx = sporeCanvas.getContext("2d");
    let spores: Spore[] = [];
    let W = (sporeCanvas.width = window.innerWidth);
    let H = (sporeCanvas.height = window.innerHeight);

    const resizeSpore = () => {
      if (sporeCanvas) {
        W = sporeCanvas.width = window.innerWidth;
        H = sporeCanvas.height = window.innerHeight;
      }
    };
    window.addEventListener("resize", resizeSpore);

    class Spore {
      x: number;
      y: number;
      life: number;
      decay: number;
      r: number;
      vx: number;
      vy: number;
      green: boolean;

      constructor(x: number, y: number) {
        this.x = x;
        this.y = y;
        this.life = 1;
        this.decay = 0.015 + Math.random() * 0.02;
        this.r = 1.5 + Math.random() * 2.5;
        this.vx = (Math.random() - 0.5) * 0.6;
        this.vy = -0.3 - Math.random() * 0.5;
        this.green = Math.random() > 0.4;
      }
      update() {
        this.x += this.vx;
        this.y += this.vy;
        this.vy *= 0.99;
        this.life -= this.decay;
      }
      draw(ctx: CanvasRenderingContext2D) {
        const alpha = this.life * 0.55;
        const color = this.green
          ? `rgba(95, 139, 76, ${alpha})`
          : `rgba(199, 242, 208, ${alpha})`;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.shadowBlur = 8;
        ctx.shadowColor = this.green ? "rgba(95,139,76,0.4)" : "rgba(199,242,208,0.4)";
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }

    const onSporeMouseMove = (e: MouseEvent) => {
      if (Math.random() > 0.55) return;
      spores.push(new Spore(e.clientX, e.clientY));
      if (spores.length > 120) spores.shift();
    };
    document.addEventListener("mousemove", onSporeMouseMove);

    let sporeFrameId = 0;
    const animateSpores = () => {
      if (sCtx) {
        sCtx.clearRect(0, 0, W, H);
        spores = spores.filter((s) => s.life > 0);
        spores.forEach((s) => {
          s.update();
          s.draw(sCtx);
        });
      }
      sporeFrameId = requestAnimationFrame(animateSpores);
    };
    animateSpores();


    // --- FOG CANVAS LOGIC ---
    const fogCanvas = fogCanvasRef.current;
    if (!fogCanvas) return;
    const fCtx = fogCanvas.getContext("2d");
    let fogW = (fogCanvas.width = fogCanvas.offsetWidth);
    let fogH = (fogCanvas.height = fogCanvas.offsetHeight);

    const resizeFog = () => {
      if (fogCanvas) {
        fogW = fogCanvas.width = fogCanvas.offsetWidth;
        fogH = fogCanvas.height = fogCanvas.offsetHeight;
      }
    };
    window.addEventListener("resize", resizeFog);

    let fogTime = 0;
    const fogLayers = Array.from({ length: 5 }, () => ({
      x: Math.random() * fogW,
      y: fogH * (0.35 + Math.random() * 0.5),
      r: 120 + Math.random() * 200,
      speed: 0.08 + Math.random() * 0.12,
      phase: Math.random() * Math.PI * 2,
      alpha: 0.025 + Math.random() * 0.025,
    }));

    let fogFrameId = 0;
    const drawFog = () => {
      if (fCtx) {
        fCtx.clearRect(0, 0, fogW, fogH);
        fogTime += 0.003;
        fogLayers.forEach((layer) => {
          const xOff = Math.sin(fogTime * layer.speed + layer.phase) * 60;
          const yOff = Math.cos(fogTime * layer.speed * 0.7 + layer.phase) * 20;
          const grad = fCtx.createRadialGradient(
            layer.x + xOff,
            layer.y + yOff,
            0,
            layer.x + xOff,
            layer.y + yOff,
            layer.r
          );
          grad.addColorStop(0, `rgba(199,242,208,${layer.alpha})`);
          grad.addColorStop(0.5, `rgba(219,231,216,${layer.alpha * 0.5})`);
          grad.addColorStop(1, "rgba(219,231,216,0)");
          fCtx.beginPath();
          fCtx.arc(layer.x + xOff, layer.y + yOff, layer.r, 0, Math.PI * 2);
          fCtx.fillStyle = grad;
          fCtx.fill();
        });
      }
      fogFrameId = requestAnimationFrame(drawFog);
    };
    drawFog();


    // --- CLEANUP ---
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseleave", onMouseLeave);
      document.removeEventListener("mouseover", onMouseOver);
      document.removeEventListener("mouseout", onMouseOut);
      document.removeEventListener("mousemove", onSporeMouseMove);
      window.removeEventListener("resize", resizeSpore);
      window.removeEventListener("resize", resizeFog);
      cancelAnimationFrame(ringFrameId);
      cancelAnimationFrame(sporeFrameId);
      cancelAnimationFrame(fogFrameId);
    };
  }, []);

  return (
    <>
      <div
        ref={cursorRef}
        id="cursor"
        style={{
          position: "fixed",
          width: "8px",
          height: "8px",
          background: "var(--dew)",
          borderRadius: "50%",
          pointerEvents: "none",
          zIndex: 9999,
          transform: "translate(-50%, -50%)",
          transition: "transform 0.1s ease, opacity 0.3s ease",
          boxShadow: "0 0 12px 4px rgba(199, 242, 208, 0.4)",
          mixBlendMode: "screen",
          opacity: 0,
        }}
      />
      <div
        ref={cursorRingRef}
        id="cursor-ring"
        style={{
          position: "fixed",
          width: "32px",
          height: "32px",
          border: "1px solid rgba(199, 242, 208, 0.3)",
          borderRadius: "50%",
          pointerEvents: "none",
          zIndex: 9998,
          transform: "translate(-50%, -50%)",
          transition: "all 0.15s ease",
          opacity: 0,
        }}
      />
      <canvas
        ref={sporeCanvasRef}
        id="spore-canvas"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: 100,
          mixBlendMode: "screen",
        }}
      />
      <canvas
        ref={fogCanvasRef}
        id="fog-canvas"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: -1,
        }}
      />
    </>
  );
}
