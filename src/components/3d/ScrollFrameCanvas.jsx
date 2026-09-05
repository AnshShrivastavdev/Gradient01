import React, { useEffect, useRef, useState, useCallback } from 'react';

const TOTAL_FRAMES = 300;

export const ScrollFrameCanvas = ({ scrollProgress, currentFrameIndex, onFrameChange }) => {
  const canvasRef = useRef(null);
  const imagesRef = useRef([]);
  const [loadedCount, setLoadedCount] = useState(0);
  const [isPreloaded, setIsPreloaded] = useState(false);
  const [displayedFrame, setDisplayedFrame] = useState(1);

  // Smooth LERP Interpolation Refs
  const smoothFrameRef = useRef(1.0);
  const animationFrameIdRef = useRef(null);

  // Preload all 300 frame images
  useEffect(() => {
    let active = true;
    let loaded = 0;
    const loadedImages = new Array(TOTAL_FRAMES);

    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image();
      const frameNum = String(i).padStart(3, '0');
      img.src = `/frames/ezgif-frame-${frameNum}.jpg`;

      img.onload = () => {
        if (!active) return;
        loaded++;
        loadedImages[i - 1] = img;
        setLoadedCount(loaded);

        if (loaded === TOTAL_FRAMES) {
          imagesRef.current = loadedImages;
          setIsPreloaded(true);
        }
      };

      img.onerror = () => {
        if (!active) return;
        loaded++;
        setLoadedCount(loaded);
        if (loaded === TOTAL_FRAMES) {
          imagesRef.current = loadedImages;
          setIsPreloaded(true);
        }
      };
    }

    return () => {
      active = false;
    };
  }, []);

  // Calculate target frame float value from scroll progress (1.0 to 300.0)
  const targetFrameFloat = Math.min(
    TOTAL_FRAMES,
    Math.max(1.0, 1.0 + scrollProgress * (TOTAL_FRAMES - 1))
  );

  const targetFrame = currentFrameIndex !== null && currentFrameIndex !== undefined
    ? Number(currentFrameIndex)
    : targetFrameFloat;

  // Ultra Crisp Dual-Frame Crossfade Canvas Rendering
  const renderSmoothFrame = useCallback((frameFloat) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    const targetW = Math.floor(rect.width * dpr);
    const targetH = Math.floor(rect.height * dpr);

    // Auto-adjust resolution for high-DPI retina sharpness
    if (canvas.width !== targetW || canvas.height !== targetH) {
      canvas.width = targetW;
      canvas.height = targetH;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Enable Maximum Image Quality Smoothing
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';

    const width = canvas.width;
    const height = canvas.height;

    // Compute Base Frame and Blend Overlay Frame
    const f1 = Math.min(TOTAL_FRAMES, Math.max(1, Math.floor(frameFloat)));
    const f2 = Math.min(TOTAL_FRAMES, f1 + 1);
    const alpha = frameFloat - Math.floor(frameFloat);

    const img1 = imagesRef.current[f1 - 1];
    const img2 = imagesRef.current[f2 - 1];

    if (!img1 || !img1.complete) return;

    // Preserve Crisp Aspect Ratio (Fill Contain)
    const imgAspect = img1.width / img1.height;
    const canvasAspect = width / height;

    let drawW, drawH, drawX, drawY;

    if (canvasAspect > imgAspect) {
      drawH = height;
      drawW = height * imgAspect;
      drawX = (width - drawW) / 2;
      drawY = 0;
    } else {
      drawW = width;
      drawH = width / imgAspect;
      drawX = 0;
      drawY = (height - drawH) / 2;
    }

    // Clear and draw Base Frame (100% opacity)
    ctx.fillStyle = '#0D1117';
    ctx.fillRect(0, 0, width, height);

    ctx.globalAlpha = 1.0;
    ctx.drawImage(img1, drawX, drawY, drawW, drawH);

    // Draw Overlay Frame with Sub-Frame Crossfade Alpha Blend
    if (alpha > 0.01 && img2 && img2.complete && f2 !== f1) {
      ctx.globalAlpha = alpha;
      ctx.drawImage(img2, drawX, drawY, drawW, drawH);
    }

    ctx.globalAlpha = 1.0;

    // Subtle Industrial Scanline Grid
    ctx.strokeStyle = 'rgba(48, 54, 61, 0.12)';
    ctx.lineWidth = 1;
    const gridSize = 48 * dpr;

    ctx.beginPath();
    for (let x = 0; x < width; x += gridSize) {
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
    }
    for (let y = 0; y < height; y += gridSize) {
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
    }
    ctx.stroke();
  }, []);

  // Continuous RAF Sub-Frame Motion Loop
  useEffect(() => {
    if (!isPreloaded) return;

    let isRunning = true;

    const updateAndRender = () => {
      if (!isRunning) return;

      const target = targetFrame;
      const current = smoothFrameRef.current;

      // Silky smooth LERP damping (0.09 factor)
      const diff = target - current;

      if (Math.abs(diff) > 0.001) {
        smoothFrameRef.current += diff * 0.09;
      } else {
        smoothFrameRef.current = target;
      }

      renderSmoothFrame(smoothFrameRef.current);

      const roundedFrame = Math.round(smoothFrameRef.current);
      setDisplayedFrame(roundedFrame);
      if (onFrameChange) onFrameChange(roundedFrame);

      animationFrameIdRef.current = requestAnimationFrame(updateAndRender);
    };

    animationFrameIdRef.current = requestAnimationFrame(updateAndRender);

    return () => {
      isRunning = false;
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current);
      }
    };
  }, [isPreloaded, targetFrame, renderSmoothFrame, onFrameChange]);

  return (
    <div className="relative w-full h-full bg-[#0D1117] overflow-hidden flex items-center justify-center select-none">
      {/* Loading overlay during frame preloading */}
      {!isPreloaded && (
        <div className="absolute inset-0 bg-[#0D1117] z-20 flex flex-col items-center justify-center p-6 text-center space-y-4 font-mono">
          <div className="w-16 h-16 border-4 border-[#30363D] border-t-[#00B4D8] animate-spin"></div>
          <p className="text-sm font-bold text-white uppercase tracking-widest">
            HYDRATING HIGH-RES 3D RENDER FRAMES: [ {loadedCount} / {TOTAL_FRAMES} ]
          </p>
          <div className="w-64 h-3 bg-[#161B22] border border-[#30363D] overflow-hidden">
            <div
              className="h-full bg-[#00B4D8] transition-all duration-150"
              style={{ width: `${(loadedCount / TOTAL_FRAMES) * 100}%` }}
            ></div>
          </div>
          <p className="text-xs text-[#8B949E]">
            PRELOAD PROTOCOL: 300 HIGH-RES 3D GEOTECHNICAL SUBSIDENCE FRAMES
          </p>
        </div>
      )}

      {/* High performance Retina 2D Canvas */}
      <canvas
        ref={canvasRef}
        className="w-full h-full object-contain block pointer-events-none"
      />
    </div>
  );
};
