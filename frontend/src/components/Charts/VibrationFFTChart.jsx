import React from 'react';

export const VibrationFFTChart = ({ vibrationAmp = 0.015 }) => {
  // Synthesize frequency spectral distribution based on current peak amplitude
  const frequencies = [
    { band: '10Hz', power: Math.min(100, vibrationAmp * 25 + 5) },
    { band: '25Hz', power: Math.min(100, vibrationAmp * 45 + 12) },
    { band: '50Hz', power: Math.min(100, vibrationAmp * 60 + 20) },
    { band: '100Hz', power: Math.min(100, vibrationAmp * 80 + 35) },
    { band: '200Hz', power: Math.min(100, vibrationAmp * 95 + 15) },
    { band: '500Hz', power: Math.min(100, vibrationAmp * 50 + 8) },
    { band: '1kHz', power: Math.min(100, vibrationAmp * 30 + 4) },
    { band: '2kHz', power: Math.min(100, vibrationAmp * 15 + 2) },
  ];

  return (
    <div className="bg-[#111827] border border-[#1F2937] p-5 rounded-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-white tracking-wide">SEISMIC FREQUENCY SPECTRUM (FFT)</h3>
          <p className="text-xs text-gray-400">Piezoelectric Micro-Seismic Spectral Density</p>
        </div>
        <span className="text-xs font-mono bg-amber-950 border border-amber-500/40 text-amber-300 px-2.5 py-0.5 rounded">
          PEAK: {vibrationAmp}g
        </span>
      </div>

      <div className="h-44 flex items-end space-x-2 pt-4 pb-2 border-b border-[#1F2937]">
        {frequencies.map((f, i) => {
          const isHigh = f.power > 60;
          return (
            <div key={i} className="flex-1 flex flex-col items-center h-full justify-end">
              <div
                style={{ height: `${f.power}%` }}
                className={`w-full rounded-t-sm transition-all duration-300 ${
                  isHigh ? 'bg-red-500 shadow-lg shadow-red-500/40' : 'bg-amber-400'
                }`}
              />
              <span className="text-[10px] font-mono text-gray-400 mt-2">{f.band}</span>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-gray-500 font-mono mt-2">
        <span>LOW FREQ (MASS SETTLEMENT)</span>
        <span>HIGH FREQ (ROCK FRACTURE)</span>
      </div>
    </div>
  );
};
