import React from 'react';
import { Compass, MoveVertical, Gauge, Zap } from 'lucide-react';

export const SensorMetricCard = ({ data = {} }) => {
  const tilt = Math.sqrt(Math.pow(data.tilt_x_deg || 0, 2) + Math.pow(data.tilt_y_deg || 0, 2)).toFixed(2);
  const disp = (data.displacement_mm || 0).toFixed(2);
  const strain = (data.strain_ue || 0).toFixed(1);
  const vib = (data.vibration_amp || 0).toFixed(4);

  const metrics = [
    {
      title: 'Tilt Inclinometer',
      sensor: 'MPU6050 (Pitch/Roll)',
      value: `${tilt}°`,
      subvalue: `X: ${data.tilt_x_deg || 0}° | Y: ${data.tilt_y_deg || 0}°`,
      icon: <Compass className="w-5 h-5 text-indigo-400" />,
      threshold: 'Max Nominal: 0.10° | Yield: >2.5°',
      barPercent: Math.min(100, (tilt / 5.0) * 100),
      color: tilt > 2.5 ? 'bg-red-500' : tilt > 0.5 ? 'bg-amber-500' : 'bg-indigo-500',
    },
    {
      title: 'Roof Displacement',
      sensor: 'VL53L4CD ToF Laser',
      value: `${disp} mm`,
      subvalue: `Vertical Subsidence Sag`,
      icon: <MoveVertical className="w-5 h-5 text-cyan-400" />,
      threshold: 'Max Nominal: 1.0mm | Yield: >20mm',
      barPercent: Math.min(100, (disp / 40.0) * 100),
      color: disp > 20 ? 'bg-red-500' : disp > 5.0 ? 'bg-amber-500' : 'bg-cyan-500',
    },
    {
      title: 'Micro-Strain Gauge',
      sensor: 'BX120-3AA + HX711',
      value: `${strain} µε`,
      subvalue: `Roof Bolt Tensile Load`,
      icon: <Gauge className="w-5 h-5 text-emerald-400" />,
      threshold: 'Max Nominal: 150µε | Yield: >400µε',
      barPercent: Math.min(100, (strain / 800.0) * 100),
      color: strain > 400 ? 'bg-red-500' : strain > 180 ? 'bg-amber-500' : 'bg-emerald-500',
    },
    {
      title: 'Seismic Vibration',
      sensor: 'Piezo + LM358 Circuit',
      value: `${vib} g`,
      subvalue: `Transient Shocks & Bursts`,
      icon: <Zap className="w-5 h-5 text-amber-400" />,
      threshold: 'Max Nominal: 0.08g | Yield: >0.80g',
      barPercent: Math.min(100, (vib / 3.0) * 100),
      color: vib > 0.8 ? 'bg-red-500' : vib > 0.1 ? 'bg-amber-500' : 'bg-amber-500',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {metrics.map((m, idx) => (
        <div key={idx} className="bg-[#111827] border border-[#1F2937] p-4 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{m.title}</span>
              <div className="p-1.5 bg-[#0B0F19] rounded-lg border border-[#1F2937]">{m.icon}</div>
            </div>
            <p className="text-2xl font-bold font-mono text-white mb-1">{m.value}</p>
            <p className="text-xs text-gray-400 mb-3">{m.subvalue}</p>
          </div>

          <div>
            <div className="w-full bg-[#0B0F19] h-2 rounded-full overflow-hidden mb-2 border border-[#1F2937]">
              <div className={`h-full transition-all duration-300 ${m.color}`} style={{ width: `${m.barPercent}%` }} />
            </div>
            <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono">
              <span>{m.sensor}</span>
              <span>{m.threshold}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
