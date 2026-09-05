import React, { useState } from 'react';

export const Footer = () => {
  const [activeModal, setActiveModal] = useState(null); // 'DGMS' | 'TOS' | 'PRIVACY' | null

  return (
    <footer className="w-full bg-[#161B22] border-t border-[#30363D] mt-auto select-none">
      <div className="max-w-7xl mx-auto px-4 py-6 flex flex-col md:flex-row items-center justify-between gap-4 text-xs font-mono text-[#8B949E]">
        {/* Left Specification */}
        <div className="space-y-1 text-center md:text-left">
          <p className="text-[#E6EDF3] font-bold">
            GRADIENT // GEOTECHNICAL GROUND-DEFORMATION MONITORING PLATFORM
          </p>
          <p>
            PHYSICAL TESTBED + LoRa SENSOR MESH + ISOLATION FOREST ANOMALY INFERENCE
          </p>
          <p className="text-[#8B949E]">
            Muster Roll Verification & Physical Ledger Cross-Validation Protocol
          </p>
        </div>

        {/* Regulatory & Legal Links */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={() => setActiveModal('DGMS')}
            className="hover:text-white underline underline-offset-4 border-b border-transparent hover:border-[#15803D]"
          >
            [ DGMS COMPLIANCE CIRCULAR 04/2021 ]
          </button>

          <button
            onClick={() => setActiveModal('TOS')}
            className="hover:text-white underline underline-offset-4 border-b border-transparent hover:border-[#8B949E]"
          >
            [ TERMS OF SERVICE ]
          </button>

          <button
            onClick={() => setActiveModal('PRIVACY')}
            className="hover:text-white underline underline-offset-4 border-b border-transparent hover:border-[#8B949E]"
          >
            [ PRIVACY POLICY ]
          </button>
        </div>
      </div>

      <div className="bg-[#0D1117] border-t border-[#30363D] py-2 text-center text-[10px] font-mono text-[#8B949E]">
        SYSTEM STATUS: OPERATIONAL | REVERSIBLE NEMA-17 MOTOR CONTROLLED | ZERO NEON GLOWS | MECHANICAL ZINC STANDARDS
      </div>

      {/* DGMS Modal */}
      {activeModal === 'DGMS' && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-[#161B22] border-2 border-[#15803D] max-w-2xl w-full p-6 text-xs font-mono space-y-4">
            <div className="flex justify-between items-center border-b border-[#30363D] pb-3">
              <h3 className="text-sm font-bold text-[#15803D] uppercase">
                DIRECTORATE GENERAL OF MINES SAFETY (DGMS) COMPLIANCE
              </h3>
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#30363D] text-white px-2 py-1 font-bold hover:bg-[#374151]"
              >
                [ CLOSE ]
              </button>
            </div>
            <div className="space-y-2 text-[#E6EDF3] leading-relaxed max-h-96 overflow-y-auto pr-2">
              <p className="font-bold text-white">REFERENCE STANDARD: DGMS (TECH) CIRCULAR NO. 04 OF 2021</p>
              <p>
                1. MANDATORY MONITORED PARAMETERS: Micro-deformation signatures, surface tilt angles (MPU6050 vector), non-contact vertical displacement (VL53L4CD ToF), and microstrain load accumulation (BX120 cantilever strain gauges).
              </p>
              <p>
                2. MUSTER ROLL INTEGRITY: All underground personnel entering longwall panel voids must possess verified entries in the physical handwritten shift register (Muster Book reference). Unverified accounts remain restricted from mobile safe link HUD access.
              </p>
              <p>
                3. EVACUATION SIREN SPECIFICATION: Automatic dual-tone 800Hz / 500Hz square-wave audio alert triggered when time-series anomaly score exceeds 0.70 (Zone C critical threshold).
              </p>
            </div>
            <div className="pt-2 border-t border-[#30363D] text-right">
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#15803D] text-white px-4 py-2 font-bold uppercase"
              >
                [ ACKNOWLEDGE COMPLIANCE ]
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Terms of Service Modal */}
      {activeModal === 'TOS' && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-[#161B22] border-2 border-[#30363D] max-w-2xl w-full p-6 text-xs font-mono space-y-4">
            <div className="flex justify-between items-center border-b border-[#30363D] pb-3">
              <h3 className="text-sm font-bold text-white uppercase">TERMS OF SERVICE</h3>
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#30363D] text-white px-2 py-1 font-bold hover:bg-[#374151]"
              >
                [ CLOSE ]
              </button>
            </div>
            <div className="space-y-2 text-[#E6EDF3] leading-relaxed max-h-96 overflow-y-auto pr-2">
              <p>1. OPERATIONAL PURPOSE: This software operates as an industrial monitoring tool for mine safety. Telemetry signals from ESP32 nodes and ToF lasers serve to support geotechnical decision-making.</p>
              <p>2. DRILL OVERRIDES: Manual drill override features are restricted to authorized Safety Incharge personnel during safety drills.</p>
            </div>
            <div className="pt-2 border-t border-[#30363D] text-right">
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#30363D] text-white px-4 py-2 font-bold uppercase"
              >
                [ I ACCEPT ]
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Privacy Policy Modal */}
      {activeModal === 'PRIVACY' && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-[#161B22] border-2 border-[#30363D] max-w-2xl w-full p-6 text-xs font-mono space-y-4">
            <div className="flex justify-between items-center border-b border-[#30363D] pb-3">
              <h3 className="text-sm font-bold text-white uppercase">PRIVACY & INDUSTRIAL DATA POLICY</h3>
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#30363D] text-white px-2 py-1 font-bold hover:bg-[#374151]"
              >
                [ CLOSE ]
              </button>
            </div>
            <div className="space-y-2 text-[#E6EDF3] leading-relaxed max-h-96 overflow-y-auto pr-2">
              <p>1. EMPLOYEE DATA: Employee IDs, names, assigned sectors, and physical register book references are stored strictly for shift muster validation and emergency dispatch.</p>
              <p>2. NO EXTERNAL DATA SHARING: Sensor data telemetry and muster logs remain within local coal mine network boundaries.</p>
            </div>
            <div className="pt-2 border-t border-[#30363D] text-right">
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#30363D] text-white px-4 py-2 font-bold uppercase"
              >
                [ UNDERSTOOD ]
              </button>
            </div>
          </div>
        </div>
      )}
    </footer>
  );
};
