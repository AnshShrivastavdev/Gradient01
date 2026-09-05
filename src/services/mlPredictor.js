/**
 * Frontend ML Risk & Zone Inference Engine
 * -----------------------------------------
 * Evaluates live sensor telemetry against calibrated geotechnical ML decision boundaries.
 */

export const classifySensorTelemetry = ({
  strainMicrostrain = 0,
  tiltDeg = 0,
  vibrationG = 0,
  displacementMm = 0,
}) => {
  // Feature Normalization based on geotechnical critical thresholds
  const strainNorm = Math.min(1.0, Math.max(0.0, strainMicrostrain / 1000.0));
  const tiltNorm = Math.min(1.0, Math.max(0.0, tiltDeg / 5.0));
  const vibNorm = Math.min(1.0, Math.max(0.0, vibrationG / 1.5));
  const dispNorm = Math.min(1.0, Math.max(0.0, displacementMm / 15.0));

  // Geotechnical Weighting derived from ML Feature Importances:
  // Vibration: 29%, Strain: 29%, Displacement: 26%, Tilt: 16%
  const compositeHazardScore = Number(
    (0.29 * vibNorm + 0.29 * strainNorm + 0.26 * dispNorm + 0.16 * tiltNorm).toFixed(3)
  );

  let predictedZone = 'ZONE_A';
  let zoneTitle = 'ZONE A // NORMAL MONITORING';
  let zoneMessage = 'SUBSURFACE STABLE. ZERO CRITICAL TURBULENCE DETECTED.';
  let badgeColor = '#15803D';
  let status = 'NOMINAL';

  // Critical conditions or anomaly score >= 0.70
  if (
    compositeHazardScore >= 0.70 ||
    strainMicrostrain >= 750 ||
    displacementMm >= 8.0 ||
    vibrationG >= 0.60 ||
    tiltDeg >= 3.0
  ) {
    predictedZone = 'ZONE_C';
    zoneTitle = 'ZONE C // CRITICAL EVACUATION';
    zoneMessage = 'CRITICAL GROUND MOVEMENT. EVACUATE CAVE IMMEDIATELY.';
    badgeColor = '#B91C1C';
    status = 'CRITICAL';
  } else if (
    compositeHazardScore >= 0.35 ||
    strainMicrostrain >= 300 ||
    displacementMm >= 2.5 ||
    vibrationG >= 0.08 ||
    tiltDeg >= 0.50
  ) {
    predictedZone = 'ZONE_B';
    zoneTitle = 'ZONE B // SEISMIC CAUTION';
    zoneMessage = 'MILD GROUND TREMORS DETECTED. PREPARE FOR POSSIBLE EVACUATION.';
    badgeColor = '#B45309';
    status = 'CAUTION';
  }

  return {
    zone: predictedZone,
    hazardScore: compositeHazardScore,
    status,
    zoneTitle,
    zoneMessage,
    badgeColor,
    metrics: {
      strainMicrostrain,
      tiltDeg,
      vibrationG,
      displacementMm,
    },
  };
};
