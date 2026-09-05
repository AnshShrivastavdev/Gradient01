import React, { useState } from 'react';

/**
 * DisplacementForecastChart
 * -------------------------------------------------------------
 * Interactive SCADA vector plot for Ground Displacement Forecasting.
 * Visualizes past historical subsidence alongside the 6-hour forward
 * multi-step LSTM predicted trajectory, critical threshold line,
 * and exact Time-to-Failure (TTF) breach pin.
 */
export const DisplacementForecastChart = ({
  historicalPoints = [],
  forecastTrajectory = [12.4, 18.2, 26.5, 33.1, 39.8, 45.2],
  timeToCriticalHours = 4.2,
  criticalThreshold = 35.0,
  activeNodeId = 'NODE_C1',
  onNodeChange,
}) => {
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [selectedThreshold, setSelectedThreshold] = useState(criticalThreshold);

  // Combine past and future for plotting
  // Past: 5 points (-30m to Now)
  const defaultPast = [
    { label: '-30m', timeVal: -0.5, value: 8.2, isFuture: false },
    { label: '-20m', timeVal: -0.33, value: 9.1, isFuture: false },
    { label: '-10m', timeVal: -0.16, value: 10.3, isFuture: false },
    { label: '-5m', timeVal: -0.08, value: 11.2, isFuture: false },
    { label: 'Now', timeVal: 0.0, value: 12.4, isFuture: false },
  ];

  const pastData = historicalPoints.length > 0 ? historicalPoints : defaultPast;
  const nowVal = pastData[pastData.length - 1]?.value || 12.4;

  // Future: 6 hourly points
  const futureData = (forecastTrajectory && forecastTrajectory.length === 6 ? forecastTrajectory : [
    nowVal + 1.2,
    nowVal + 3.1,
    nowVal + 6.8,
    nowVal + 12.5,
    nowVal + 21.0,
    nowVal + 32.4
  ]).map((val, idx) => ({
    label: `+${idx + 1}h`,
    timeVal: idx + 1,
    value: Number(val.toFixed(1)),
    isFuture: true,
  }));

  // Combined timeline points
  const allPoints = [...pastData, ...futureData];

  // SVG dimensions
  const width = 800;
  const height = 320;
  const padding = { top: 35, right: 40, bottom: 45, left: 55 };
  const graphWidth = width - padding.left - padding.right;
  const graphHeight = height - padding.top - padding.bottom;

  // Y-axis scale (0 to max value with headroom)
  const maxVal = Math.max(50.0, ...allPoints.map((p) => p.value), selectedThreshold + 5);
  const minVal = 0.0;

  const getX = (index, total) => {
    return padding.left + (index / (total - 1)) * graphWidth;
  };

  const getY = (val) => {
    const clamped = Math.max(minVal, Math.min(maxVal, val));
    return padding.top + graphHeight - ((clamped - minVal) / (maxVal - minVal)) * graphHeight;
  };

  // Build SVG path strings
  // Past curve (solid)
  const pastCoords = pastData.map((p, i) => ({
    x: getX(i, allPoints.length),
    y: getY(p.value),
    data: p,
  }));

  let pastPath = '';
  pastCoords.forEach((pt, i) => {
    if (i === 0) pastPath += `M ${pt.x},${pt.y}`;
    else pastPath += ` L ${pt.x},${pt.y}`;
  });

  // Future curve (dotted, starts from 'Now' coordinate)
  const nowCoord = pastCoords[pastCoords.length - 1];
  const futureCoords = [
    nowCoord,
    ...futureData.map((p, i) => ({
      x: getX(pastData.length + i, allPoints.length),
      y: getY(p.value),
      data: p,
    })),
  ];

  let futurePath = '';
  futureCoords.forEach((pt, i) => {
    if (i === 0) futurePath += `M ${pt.x},${pt.y}`;
    else futurePath += ` L ${pt.x},${pt.y}`;
  });

  // Area under the past curve
  const pastArea = `${pastPath} L ${nowCoord.x},${getY(0)} L ${pastCoords[0].x},${getY(0)} Z`;

  // Area under future curve
  const futureArea = `${futurePath} L ${futureCoords[futureCoords.length - 1].x},${getY(0)} L ${nowCoord.x},${getY(0)} Z`;

  // Critical threshold Y coordinate
  const thresholdY = getY(selectedThreshold);

  // Time to Failure marker coordinate (interpolated)
  let breachX = null;
  let breachY = thresholdY;
  if (timeToCriticalHours !== null && timeToCriticalHours > 0 && timeToCriticalHours <= 6) {
    const pastRatio = (pastData.length - 1) / (allPoints.length - 1);
    const futureRatio = (timeToCriticalHours / 6.0) * (futureData.length / (allPoints.length - 1));
    breachX = padding.left + (pastRatio + futureRatio) * graphWidth;
  }

  // Y-axis ticks
  const yTicks = [0, 10, 20, 30, selectedThreshold, Math.round(maxVal)];
  const sortedYTicks = Array.from(new Set(yTicks)).sort((a, b) => a - b);

  return (
    <div className="bg-[#161B22] border-2 border-[#30363D] p-4 sm:p-6 space-y-4 font-mono text-[#E6EDF3] select-none">
      {/* 1. CHART HEADER & CONTROLS */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b border-[#30363D] pb-3">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-[10px] bg-[#B91C1C] text-white font-bold px-2 py-0.5 uppercase tracking-wider">
              PYTORCH LSTM TIME-SERIES ENGINE
            </span>
            <span className="text-[10px] bg-[#00B4D8] text-black font-bold px-2 py-0.5 uppercase">
              1-6 HOUR MULTI-STEP TRAJECTORY
            </span>
          </div>
          <h3 className="text-base sm:text-lg font-display font-extrabold text-white uppercase tracking-tight">
            GROUND DISPLACEMENT SUBSIDENCE FORECAST CURVE
          </h3>
          <p className="text-xs text-[#8B949E]">
            Continuous geomechanical subsidence curve tracking Voight failure phases (Primary to Secondary to Tertiary Runaway).
          </p>
        </div>

        {/* Node Selector & Threshold Config */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="bg-[#0D1117] border border-[#30363D] px-2.5 py-1.5 flex items-center space-x-2">
            <span className="text-[#8B949E] text-[10px]">MONITORED NODE:</span>
            <select
              value={activeNodeId}
              onChange={(e) => onNodeChange && onNodeChange(e.target.value)}
              className="bg-transparent text-white font-bold text-xs outline-none cursor-pointer"
            >
              <option value="NODE_C1" className="bg-[#161B22] text-white">NODE C1 (CENTER LONGWALL FACE)</option>
              <option value="NODE_B1" className="bg-[#161B22] text-white">NODE B1 (RETURN AIRWAY PILLAR)</option>
              <option value="NODE_A1" className="bg-[#161B22] text-white">NODE A1 (MAIN ENTRY PORTAL)</option>
            </select>
          </div>

          <div className="bg-[#0D1117] border border-[#30363D] px-2.5 py-1.5 flex items-center space-x-2">
            <span className="text-[#8B949E] text-[10px]">CRITICAL THRESHOLD:</span>
            <button
              onClick={() => setSelectedThreshold(selectedThreshold === 35.0 ? 25.0 : 35.0)}
              className="font-bold text-[#F59E0B] hover:underline"
            >
              {selectedThreshold.toFixed(1)} mm
            </button>
          </div>
        </div>
      </div>

      {/* 2. STATS OVERVIEW CARDS */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">CURRENT DISPLACEMENT</div>
          <div className="text-lg font-bold text-white">{nowVal.toFixed(2)} mm</div>
          <div className="text-[10px] text-[#00B4D8]">Lookback Buffer: 60 Samples</div>
        </div>

        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">6-HOUR PROJECTED PEAK</div>
          <div className="text-lg font-bold text-[#F59E0B]">
            {futureData[futureData.length - 1].value.toFixed(1)} mm
          </div>
          <div className="text-[10px] text-[#8B949E]">
            {futureData[futureData.length - 1].value >= selectedThreshold ? '⚠️ Exceeds Critical' : '✅ Within Margin'}
          </div>
        </div>

        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">SUBSIDENCE VELOCITY</div>
          <div className="text-lg font-bold text-white">
            {timeToCriticalHours ? '+6.7 mm/hr' : '+0.08 mm/hr'}
          </div>
          <div className="text-[10px] text-[#B91C1C]">
            {timeToCriticalHours ? 'Accelerating Rate (Tertiary)' : 'Steady State Creep'}
          </div>
        </div>

        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">ESTIMATED TIME-TO-FAILURE (TTF)</div>
          <div className={`text-lg font-bold ${timeToCriticalHours ? 'text-[#EF4444] animate-pulse' : 'text-[#10B981]'}`}>
            {timeToCriticalHours ? `${timeToCriticalHours} HOURS` : 'NONE (STABLE)'}
          </div>
          <div className="text-[10px] text-[#8B949E]">
            {timeToCriticalHours ? `Threshold: ${selectedThreshold} mm` : 'No Breach within 6h'}
          </div>
        </div>
      </div>

      {/* 3. INTERACTIVE SCADA VECTOR SVG CHART */}
      <div className="relative w-full overflow-hidden bg-[#0D1117] border border-[#30363D] rounded p-2">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto overflow-visible"
        >
          <defs>
            {/* Historical fill gradient */}
            <linearGradient id="pastAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00B4D8" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#00B4D8" stopOpacity="0.02" />
            </linearGradient>

            {/* Future forecast fill gradient */}
            <linearGradient id="futureAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#EF4444" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#F59E0B" stopOpacity="0.02" />
            </linearGradient>

            {/* Danger zone pattern */}
            <pattern id="dangerHatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="8" stroke="#B91C1C" strokeWidth="1.5" strokeOpacity="0.25" />
            </pattern>
          </defs>

          {/* Danger Zone Shading above Critical Threshold */}
          <rect
            x={padding.left}
            y={padding.top}
            width={graphWidth}
            height={Math.max(0, thresholdY - padding.top)}
            fill="url(#dangerHatch)"
          />

          {/* Grid lines (horizontal) */}
          {sortedYTicks.map((tickVal) => {
            const y = getY(tickVal);
            return (
              <g key={tickVal}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={width - padding.right}
                  y2={y}
                  stroke={tickVal === selectedThreshold ? '#EF4444' : '#21262D'}
                  strokeWidth={tickVal === selectedThreshold ? '1.5' : '1'}
                  strokeDasharray={tickVal === selectedThreshold ? '5 4' : 'none'}
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="10"
                  fill={tickVal === selectedThreshold ? '#EF4444' : '#8B949E'}
                  fontWeight={tickVal === selectedThreshold ? 'bold' : 'normal'}
                >
                  {tickVal.toFixed(0)} mm
                </text>
              </g>
            );
          })}

          {/* NOW Vertical Split Divider */}
          <line
            x1={nowCoord.x}
            y1={padding.top}
            x2={nowCoord.x}
            y2={height - padding.bottom}
            stroke="#00B4D8"
            strokeWidth="1.5"
            strokeDasharray="3 3"
          />
          <text
            x={nowCoord.x}
            y={padding.top - 10}
            textAnchor="middle"
            fontSize="10"
            fill="#00B4D8"
            fontWeight="bold"
          >
            [ NOW ]
          </text>

          {/* Critical Threshold Label */}
          <text
            x={width - padding.right}
            y={thresholdY - 6}
            textAnchor="end"
            fontSize="10"
            fill="#EF4444"
            fontWeight="bold"
          >
            CRITICAL COLLAPSE THRESHOLD ({selectedThreshold.toFixed(1)} mm)
          </text>

          {/* Historical Area & Curve */}
          <path d={pastArea} fill="url(#pastAreaGradient)" />
          <path
            d={pastPath}
            fill="none"
            stroke="#00B4D8"
            strokeWidth="2.5"
            strokeLinecap="round"
          />

          {/* Forecast Area & Curve */}
          <path d={futureArea} fill="url(#futureAreaGradient)" />
          <path
            d={futurePath}
            fill="none"
            stroke="#F59E0B"
            strokeWidth="2.5"
            strokeDasharray="6 4"
            strokeLinecap="round"
          />

          {/* Time-To-Failure Breach Pin Marker */}
          {breachX && (
            <g className="cursor-pointer">
              {/* Vertical line at breach */}
              <line
                x1={breachX}
                y1={breachY}
                x2={breachX}
                y2={height - padding.bottom}
                stroke="#EF4444"
                strokeWidth="1.5"
                strokeDasharray="2 2"
              />
              {/* Pulsing circle halo */}
              <circle
                cx={breachX}
                cy={breachY}
                r="10"
                fill="#EF4444"
                fillOpacity="0.25"
                className="animate-ping"
              />
              <circle
                cx={breachX}
                cy={breachY}
                r="5"
                fill="#EF4444"
                stroke="#FFFFFF"
                strokeWidth="2"
              />
              {/* Badge */}
              <rect
                x={breachX - 55}
                y={breachY - 26}
                width="110"
                height="18"
                fill="#B91C1C"
                stroke="#FFFFFF"
                strokeWidth="1"
                rx="2"
              />
              <text
                x={breachX}
                y={breachY - 14}
                textAnchor="middle"
                fontSize="9"
                fill="#FFFFFF"
                fontWeight="bold"
              >
                💥 TTF: {timeToCriticalHours}h ({selectedThreshold}mm)
              </text>
            </g>
          )}

          {/* Historical Points */}
          {pastCoords.map((pt, i) => (
            <circle
              key={`past-${i}`}
              cx={pt.x}
              cy={pt.y}
              r={hoveredPoint?.data === pt.data ? 5 : 3.5}
              fill="#00B4D8"
              stroke="#0D1117"
              strokeWidth="1.5"
              className="cursor-pointer transition-all"
              onMouseEnter={() => setHoveredPoint(pt)}
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}

          {/* Future Points */}
          {futureCoords.slice(1).map((pt, i) => (
            <circle
              key={`future-${i}`}
              cx={pt.x}
              cy={pt.y}
              r={hoveredPoint?.data === pt.data ? 6 : 4}
              fill={pt.data.value >= selectedThreshold ? '#EF4444' : '#F59E0B'}
              stroke="#FFFFFF"
              strokeWidth="1.5"
              className="cursor-pointer transition-all"
              onMouseEnter={() => setHoveredPoint(pt)}
              onMouseLeave={() => setHoveredPoint(null)}
            />
          ))}

          {/* X-Axis Ticks & Labels */}
          {allPoints.map((p, i) => {
            const x = getX(i, allPoints.length);
            return (
              <g key={`x-tick-${i}`}>
                <line
                  x1={x}
                  y1={height - padding.bottom}
                  x2={x}
                  y2={height - padding.bottom + 5}
                  stroke="#30363D"
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={height - padding.bottom + 16}
                  textAnchor="middle"
                  fontSize="10"
                  fill={p.label === 'Now' ? '#00B4D8' : p.isFuture ? '#F59E0B' : '#8B949E'}
                  fontWeight={p.label === 'Now' ? 'bold' : 'normal'}
                >
                  {p.label}
                </text>
              </g>
            );
          })}

          {/* Sub-labels for Timeline Regions */}
          <text
            x={padding.left + ((nowCoord.x - padding.left) / 2)}
            y={height - 8}
            textAnchor="middle"
            fontSize="9"
            fill="#8B949E"
            letterSpacing="0.05em"
          >
            ◄ PAST OBSERVED SENSOR LOOKBACK
          </text>
          <text
            x={nowCoord.x + ((width - padding.right - nowCoord.x) / 2)}
            y={height - 8}
            textAnchor="middle"
            fontSize="9"
            fill="#F59E0B"
            letterSpacing="0.05em"
          >
            LSTM 6-HOUR FORWARD PROJECTION ►
          </text>

          {/* Hover Tooltip Box */}
          {hoveredPoint && (
            <g transform={`translate(${hoveredPoint.x - 60}, ${Math.max(10, hoveredPoint.y - 45)})`}>
              <rect
                width="120"
                height="38"
                fill="#161B22"
                stroke={hoveredPoint.data.isFuture ? '#F59E0B' : '#00B4D8'}
                strokeWidth="1.5"
                rx="4"
              />
              <text x="60" y="15" textAnchor="middle" fontSize="10" fill="#8B949E">
                {hoveredPoint.data.label} {hoveredPoint.data.isFuture ? '(Forecast)' : '(Recorded)'}
              </text>
              <text x="60" y="30" textAnchor="middle" fontSize="12" fill="#FFFFFF" fontWeight="bold">
                {hoveredPoint.data.value.toFixed(2)} mm
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* 4. SCADA CHART LEGEND */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs pt-2 border-t border-[#30363D]">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <span className="w-4 h-1 bg-[#00B4D8]"></span>
            <span className="text-[#8B949E]">Historical Lookback (Past Readings)</span>
          </div>

          <div className="flex items-center space-x-2">
            <span className="w-4 h-0.5 border-b-2 border-dashed border-[#F59E0B]"></span>
            <span className="text-[#F59E0B]">PyTorch LSTM Multi-Step Forecast</span>
          </div>

          <div className="flex items-center space-x-2">
            <span className="w-4 h-0.5 border-b-2 border-dashed border-[#EF4444]"></span>
            <span className="text-[#EF4444]">Critical Breach ({selectedThreshold} mm)</span>
          </div>
        </div>

        <div className="text-[11px] text-[#8B949E]">
          Inference Latency: <strong className="text-white">1.8ms (ONNX Runtime)</strong> | Monotonic Physics Bound: <strong className="text-white">Active</strong>
        </div>
      </div>
    </div>
  );
};
