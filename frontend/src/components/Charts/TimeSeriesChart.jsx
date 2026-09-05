import React, { useEffect, useState } from 'react';

export const TimeSeriesChart = ({ currentData = {} }) => {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (currentData.strain_ue !== undefined) {
      setHistory((prev) => {
        const next = [
          ...prev,
          {
            time: new Date().toLocaleTimeString().split(' ')[0],
            strain: currentData.strain_ue || 0,
            disp: currentData.displacement_mm || 0,
            tilt: Math.sqrt(Math.pow(currentData.tilt_x_deg || 0, 2) + Math.pow(currentData.tilt_y_deg || 0, 2)),
          },
        ];
        return next.slice(-20); // Keep last 20 ticks
      });
    }
  }, [currentData]);

  const maxStrain = Math.max(800, ...history.map((h) => h.strain));

  return (
    <div className="bg-[#111827] border border-[#1F2937] p-5 rounded-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold text-white tracking-wide">REAL-TIME TIME-SERIES TELEMETRY STREAM</h3>
          <p className="text-xs text-gray-400">Continuous 1Hz Multi-Sensor Rolling Trajectory</p>
        </div>
        <div className="flex items-center space-x-4 text-xs font-mono">
          <span className="flex items-center gap-1 text-emerald-400"><span className="w-2 h-2 rounded-full bg-emerald-400" /> Strain (µε)</span>
          <span className="flex items-center gap-1 text-cyan-400"><span className="w-2 h-2 rounded-full bg-cyan-400" /> Disp (mm)</span>
          <span className="flex items-center gap-1 text-indigo-400"><span className="w-2 h-2 rounded-full bg-indigo-400" /> Tilt (°)</span>
        </div>
      </div>

      <div className="h-44 flex items-end space-x-1.5 pt-4 pb-2 border-b border-[#1F2937]">
        {history.map((pt, i) => {
          const strainHeight = Math.min(100, (pt.strain / maxStrain) * 100);
          const dispHeight = Math.min(100, (pt.disp / 40) * 100);

          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-1 h-full justify-end group relative">
              {/* Tooltip */}
              <div className="absolute -top-10 hidden group-hover:flex flex-col bg-gray-900 border border-gray-700 p-1.5 rounded text-[10px] text-white z-10 whitespace-nowrap shadow-lg">
                <span>{pt.time}</span>
                <span>Strain: {pt.strain}µε | Disp: {pt.disp}mm</span>
              </div>

              <div className="w-full flex justify-center gap-0.5 items-end h-full">
                <div style={{ height: `${strainHeight}%` }} className="w-1/2 bg-emerald-500 rounded-t-sm transition-all duration-200" />
                <div style={{ height: `${dispHeight}%` }} className="w-1/2 bg-cyan-500 rounded-t-sm transition-all duration-200" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between text-[10px] text-gray-500 font-mono mt-2">
        <span>-20s AGO</span>
        <span>LIVE (1 Hz)</span>
      </div>
    </div>
  );
};
