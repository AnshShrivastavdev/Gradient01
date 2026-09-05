import React from 'react';
import { AlertTriangle, AlertOctagon, BellRing } from 'lucide-react';
import { useTelemetryContext } from '../context/WebSocketContext';

export const AlertBanner = () => {
  const { telemetry } = useTelemetryContext();
  const nodes = Object.values(telemetry);

  const criticalNode = nodes.find((n) => n.predicted_risk === 'Critical');
  const warningNode = nodes.find((n) => n.predicted_risk === 'Warning');

  if (criticalNode) {
    return (
      <div className="bg-red-900/90 border-y border-red-500 text-white px-6 py-3 flex items-center justify-between shadow-lg shadow-red-950/50 animate-pulse">
        <div className="flex items-center space-x-3">
          <AlertOctagon className="w-6 h-6 text-red-300" />
          <div>
            <h2 className="text-sm font-bold tracking-wide">
              ZONE C DANGER // IMMINENT SUBSIDENCE COLLAPSE DETECTED
            </h2>
            <p className="text-xs text-red-200">
              Sector {criticalNode.zone_id} ({criticalNode.node_id}): Micro-strain {criticalNode.strain_ue}µε, Disp {criticalNode.displacement_mm}mm, Tilt {criticalNode.tilt_x_deg}°. Sounding automatic evacuation sirens.
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2 bg-red-950 px-3 py-1 rounded border border-red-400">
          <BellRing className="w-4 h-4 text-red-300 animate-spin" />
          <span className="text-xs font-mono font-bold text-red-200">EVACUATE NOW</span>
        </div>
      </div>
    );
  }

  if (warningNode) {
    return (
      <div className="bg-amber-900/80 border-y border-amber-500 text-white px-6 py-2.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <AlertTriangle className="w-5 h-5 text-amber-300" />
          <div>
            <h2 className="text-sm font-semibold">ZONE B CAUTION // SEISMIC TREMOR BURSTS & PROGRESSIVE SAG</h2>
            <p className="text-xs text-amber-200">
              Sector {warningNode.zone_id} ({warningNode.node_id}): Elevated micro-strain {warningNode.strain_ue}µε. Safety inspection crew alerted.
            </p>
          </div>
        </div>
        <span className="text-xs font-mono bg-amber-950 px-2.5 py-1 rounded border border-amber-500 text-amber-300">
          INSPECTION REQUIRED
        </span>
      </div>
    );
  }

  return null;
};
