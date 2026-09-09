import React, { useState, useEffect, useRef } from 'react';
import { ScrollFrameCanvas } from '../components/3d/ScrollFrameCanvas';
import { useTelemetry } from '../context/TelemetryContext';

export const LandingPage = ({ onOpenAuth, onOpenDashboard }) => {
  const { telemetry } = useTelemetry();
  const [scrollProgress, setScrollProgress] = useState(0);
  const [currentScene, setCurrentScene] = useState(1);
  const [manualFrame, setManualFrame] = useState(null);

  const containerRef = useRef(null);

  // Monitor Scroll Progress across the 5 Storytelling Scenes
  useEffect(() => {
    const handleScroll = () => {
      const el = containerRef.current;
      if (!el) return;

      const scrollTop = window.scrollY;
      const docHeight = el.scrollHeight - window.innerHeight;
      if (docHeight <= 0) return;

      const progress = Math.min(1.0, Math.max(0.0, scrollTop / docHeight));
      setScrollProgress(progress);

      if (progress < 0.15) setCurrentScene(1);
      else if (progress < 0.40) setCurrentScene(2);
      else if (progress < 0.65) setCurrentScene(3);
      else if (progress < 0.85) setCurrentScene(4);
      else setCurrentScene(5);

      setManualFrame(null);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const jumpToScene = (sceneNum) => {
    let targetFrame = 1;
    let targetProgress = 0;

    if (sceneNum === 1) { targetProgress = 0.05; targetFrame = 15; }
    else if (sceneNum === 2) { targetProgress = 0.25; targetFrame = 75; }
    else if (sceneNum === 3) { targetProgress = 0.50; targetFrame = 150; }
    else if (sceneNum === 4) { targetProgress = 0.75; targetFrame = 225; }
    else if (sceneNum === 5) { targetProgress = 0.95; targetFrame = 285; }

    setManualFrame(targetFrame);
    setCurrentScene(sceneNum);

    const el = containerRef.current;
    if (el) {
      const docHeight = el.scrollHeight - window.innerHeight;
      window.scrollTo({
        top: targetProgress * docHeight,
        behavior: 'smooth',
      });
    }
  };

  return (
    <div ref={containerRef} className="relative w-full bg-[#0D1117] text-[#E6EDF3] font-mono select-none">
      {/* Background 3D Storytelling Canvas */}
      <div className="fixed inset-0 w-full h-screen z-0">
        <ScrollFrameCanvas
          scrollProgress={scrollProgress}
          currentFrameIndex={manualFrame}
        />
      </div>

      {/* Scene Selector Toolbar */}
      <div className="fixed bottom-24 right-6 z-40 bg-[#161B22]/90 border border-[#30363D] p-2 flex flex-col space-y-2 text-xs">
        <div className="flex justify-between items-center text-[10px] text-[#8B949E] uppercase font-bold border-b border-[#30363D] pb-1 space-x-4">
          <span>SCENE 0{currentScene} / 05</span>
          <span className="text-[#00B4D8] font-semibold">[3D SCROLL ENGINE]</span>
        </div>
        <div className="flex space-x-1">
          {[1, 2, 3, 4, 5].map((s) => (
            <button
              key={s}
              onClick={() => jumpToScene(s)}
              className={`px-2.5 py-1 text-xs border transition-colors ${
                currentScene === s
                  ? 'bg-[#30363D] text-white border-white font-bold'
                  : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
              }`}
            >
              0{s}
            </button>
          ))}
        </div>
      </div>

      {/* Clean Minimal Storytelling Overlay Cards */}
      <div className="relative z-10 w-full space-y-32 py-12">
        {/* STORY SCENE 1: Hazard Overview */}
        <section className="min-h-screen flex items-center justify-start p-6 md:p-16 max-w-2xl">
          <div className="bg-[#161B22]/90 border-2 border-[#30363D] p-6 space-y-4">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-ping"></span>
              <span className="text-[10px] font-bold tracking-widest text-[#00B4D8] uppercase">TEAM GRADIENT // SIH 2026</span>
            </div>
            <h2 className="text-xl md:text-2xl font-display font-extrabold text-white leading-snug">
              PREDICTIVE SUBSURFACE DEFORMATION & PANEL SUBSIDENCE
            </h2>
            <p className="text-xs text-[#E6EDF3] leading-relaxed">
              Underground longwall mining creates subterranean voids that induce surface subsidence. The system correlates physical testbed telemetry, distributed LoRa sensor meshes, and unsupervised AI to flag early micro-deformation prior to collapse.
            </p>
            <div className="pt-2 flex flex-wrap items-center gap-3">
              <button
                onClick={onOpenDashboard}
                className="px-5 py-2.5 bg-[#00B4D8] text-black font-bold text-xs uppercase border border-white hover:bg-cyan-400 transition-colors shadow-lg"
              >
                [ 🚀 OPEN LIVE DASHBOARD ]
              </button>
              <button
                onClick={() => jumpToScene(2)}
                className="px-4 py-2.5 bg-[#0D1117] text-[#8B949E] font-bold text-xs uppercase border border-[#30363D] hover:text-white transition-colors"
              >
                [ SCROLL 3D RIG ↓ ]
              </button>
            </div>
          </div>
        </section>

        {/* STORY SCENE 2: The Physical Rig */}
        <section className="min-h-screen flex items-center justify-end p-6 md:p-16 max-w-7xl mx-auto">
          <div className="bg-[#161B22]/90 border-2 border-[#30363D] p-6 max-w-xl space-y-3">
            <h2 className="text-lg md:text-xl font-display font-extrabold text-white">
              SEGMENTED TRI-ZONE SUBSIDENCE CHAMBER
            </h2>
            <p className="text-xs text-[#E6EDF3] leading-relaxed">
              A transparent acrylic enclosure physically models panel support loss. A single reversible NEMA-17 stepper motor lowers the central platform (Zone B) in sub-millimeter increments, creating controlled granular displacement relative to fixed reference platforms (Zones A & C).
            </p>
          </div>
        </section>

        {/* STORY SCENE 3: Distributed Instrumentation */}
        <section className="min-h-screen flex items-center justify-start p-6 md:p-16 max-w-7xl mx-auto">
          <div className="bg-[#161B22]/90 border-2 border-[#30363D] p-6 max-w-2xl space-y-3">
            <h2 className="text-lg md:text-xl font-display font-extrabold text-white">
              MULTI-SENSOR TELEMETRY MESH
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              <div className="bg-[#0D1117] border border-[#30363D] p-2.5">
                <div className="text-white font-bold">1. ESP32 + MPU6500 INCLINOMETERS</div>
                <div className="text-[11px] text-[#8B949E]">Baseline reference & tilt vectors.</div>
              </div>
              <div className="bg-[#0D1117] border border-[#30363D] p-2.5">
                <div className="text-white font-bold">2. VL53L4CD ToF LASER</div>
                <div className="text-[11px] text-[#8B949E]">Direct millimeter vertical distance.</div>
              </div>
              <div className="bg-[#0D1117] border border-[#30363D] p-2.5">
                <div className="text-white font-bold">3. BX120 STRAIN GAUGES</div>
                <div className="text-[11px] text-[#8B949E]">Microstrain load on cantilever strip.</div>
              </div>
              <div className="bg-[#0D1117] border border-[#30363D] p-2.5">
                <div className="text-white font-bold">4. LoRa SX1276 (868 MHz)</div>
                <div className="text-[11px] text-[#8B949E]">Long-range gateway transmission.</div>
              </div>
            </div>
          </div>
        </section>

        {/* STORY SCENE 4: AI Anomaly Inference Engine */}
        <section className="min-h-screen flex items-center justify-end p-6 md:p-16 max-w-7xl mx-auto">
          <div className="bg-[#161B22]/90 border-2 border-[#30363D] p-6 max-w-xl space-y-3">
            <h2 className="text-lg md:text-xl font-display font-extrabold text-white">
              ISOLATION FOREST ANOMALY ENGINE
            </h2>
            <p className="text-xs text-[#E6EDF3] leading-relaxed">
              Computes spatial tilt deltas, acceleration spikes, microstrain, and vertical distance. An unsupervised Isolation Forest flags baseline departures to classify hazards into Zone A (Nominal), Zone B (Caution), and Zone C (Critical).
            </p>
          </div>
        </section>

        {/* STORY SCENE 5: Portal Gateway & Login/Signup Prompt */}
        <section className="min-h-screen flex items-center justify-center p-6 md:p-16 max-w-4xl mx-auto">
          <div className="bg-[#161B22]/95 border-2 border-[#30363D] p-8 w-full max-w-2xl text-center space-y-5">
            <h2 className="text-2xl font-display font-extrabold text-white uppercase">
              ENTER COAL MINE MONITORING SYSTEM
            </h2>
            <p className="text-xs text-[#8B949E]">
              Role-Based Access Control integrated with physical shift muster roll ledger verification.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <button
                onClick={onOpenDashboard}
                className="w-full sm:w-auto px-6 py-3.5 bg-[#00B4D8] text-black font-bold text-xs uppercase border border-white hover:bg-cyan-400 transition-colors shadow-lg"
              >
                [ DIRECT TO LIVE DASHBOARD → ]
              </button>
              <button
                onClick={() => onOpenAuth('WORKER_LOGIN')}
                className="w-full sm:w-auto px-6 py-3.5 bg-[#15803D] text-white font-bold text-xs uppercase border border-white hover:bg-green-700 transition-colors"
              >
                [ LOG IN TO SYSTEM ]
              </button>
              <button
                onClick={() => onOpenAuth('WORKER_REGISTER')}
                className="w-full sm:w-auto px-6 py-3.5 bg-[#30363D] text-white font-bold text-xs uppercase border border-[#374151] hover:bg-[#374151] transition-colors"
              >
                [ REGISTER NEW WORKER ]
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
