import React, { useRef, useMemo, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Float, Stars, Text, MeshTransmissionMaterial } from '@react-three/drei';
import * as THREE from 'three';

// ================================================================
// COAL MINE 3D SCENE — Team Gradient SIH 2026
// Procedural underground mine with live sensor nodes,
// subsidence deformation, LoRa signal waves, and dust particles.
// ================================================================

// ─── Color Palette (matches SCADA UI) ───
const COLORS = {
  bg: '#0D1117',
  terrain: '#1a1a2e',
  terrainEdge: '#0f3460',
  zoneA: '#15803D',
  zoneB: '#B45309',
  zoneC: '#B91C1C',
  cyan: '#00B4D8',
  grid: '#30363D',
  rock: '#2d2d3d',
  lava: '#ff6b35',
  dust: '#8B949E',
  sensorGlow: '#00B4D8',
};

// ─── Procedural Terrain Mesh ───
function TerrainLayer({ yOffset = 0, color = COLORS.terrain, wireframe = false, opacity = 1 }) {
  const meshRef = useRef();
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(40, 40, 80, 80);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      // Procedural heightmap: rolling hills with central subsidence basin
      const distFromCenter = Math.sqrt(x * x + y * y);
      const basin = Math.max(0, 1 - distFromCenter / 8) * -2.5;
      const noise = Math.sin(x * 0.8) * Math.cos(y * 0.6) * 0.6
        + Math.sin(x * 1.5 + y * 0.7) * 0.3
        + Math.cos(x * 0.3 - y * 1.2) * 0.4;
      pos.setZ(i, noise + basin + yOffset);
    }
    g.computeVertexNormals();
    return g;
  }, [yOffset]);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.material.emissiveIntensity = 0.08 + Math.sin(clock.elapsedTime * 0.5) * 0.03;
    }
  });

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, yOffset, 0]} geometry={geo}>
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.08}
        wireframe={wireframe}
        transparent={opacity < 1}
        opacity={opacity}
        side={THREE.DoubleSide}
        roughness={0.85}
        metalness={0.15}
      />
    </mesh>
  );
}

// ─── Subsidence Zone Rings ───
function SubsidenceZone({ position, radius, color, label, pulseSpeed = 1 }) {
  const ringRef = useRef();
  const glowRef = useRef();

  useFrame(({ clock }) => {
    if (ringRef.current) {
      const s = 1 + Math.sin(clock.elapsedTime * pulseSpeed) * 0.06;
      ringRef.current.scale.set(s, s, 1);
    }
    if (glowRef.current) {
      glowRef.current.material.opacity = 0.15 + Math.sin(clock.elapsedTime * pulseSpeed * 1.5) * 0.1;
    }
  });

  return (
    <group position={position}>
      {/* Zone fill disc */}
      <mesh ref={glowRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <circleGeometry args={[radius, 64]} />
        <meshBasicMaterial color={color} transparent opacity={0.12} side={THREE.DoubleSide} />
      </mesh>

      {/* Zone ring border */}
      <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}>
        <ringGeometry args={[radius - 0.08, radius, 64]} />
        <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>

      {/* Zone label */}
      <Text
        position={[0, 0.3, radius + 0.5]}
        fontSize={0.35}
        color={color}
        anchorX="center"
        anchorY="middle"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
      >
        {label}
      </Text>
    </group>
  );
}

// ─── Sensor Node (ESP32 + MPU6500) ───
function SensorNode({ position, nodeId, color = COLORS.sensorGlow, isActive = true }) {
  const groupRef = useRef();
  const beamRef = useRef();
  const pulseRef = useRef();

  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.position.y = position[1] + Math.sin(clock.elapsedTime * 2 + position[0]) * 0.05;
    }
    if (beamRef.current) {
      beamRef.current.material.opacity = isActive ? 0.4 + Math.sin(clock.elapsedTime * 3) * 0.2 : 0.05;
    }
    if (pulseRef.current) {
      const s = 1 + Math.sin(clock.elapsedTime * 4) * 0.3;
      pulseRef.current.scale.set(s, s, s);
      pulseRef.current.material.opacity = isActive ? 0.6 - Math.sin(clock.elapsedTime * 4) * 0.3 : 0.1;
    }
  });

  return (
    <group ref={groupRef} position={position}>
      {/* PCB board */}
      <mesh>
        <boxGeometry args={[0.5, 0.12, 0.35]} />
        <meshStandardMaterial color="#1a472a" emissive="#0a2f1a" emissiveIntensity={0.3} metalness={0.6} roughness={0.4} />
      </mesh>

      {/* Chip (MPU6500) */}
      <mesh position={[0, 0.08, 0]}>
        <boxGeometry args={[0.15, 0.04, 0.15]} />
        <meshStandardMaterial color="#111" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Antenna */}
      <mesh position={[0.18, 0.2, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 0.3, 8]} />
        <meshStandardMaterial color="#888" metalness={0.8} roughness={0.3} />
      </mesh>

      {/* Status LED glow */}
      <mesh ref={pulseRef} position={[-0.15, 0.08, 0.1]}>
        <sphereGeometry args={[0.04, 16, 16]} />
        <meshBasicMaterial color={isActive ? color : '#333'} transparent opacity={0.6} />
      </mesh>

      {/* Vertical data beam */}
      <mesh ref={beamRef} position={[0, 1.2, 0]}>
        <cylinderGeometry args={[0.02, 0.06, 2.2, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.3} />
      </mesh>

      {/* Node ID label */}
      <Text
        position={[0, -0.25, 0]}
        fontSize={0.15}
        color={color}
        anchorX="center"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
      >
        {nodeId}
      </Text>
    </group>
  );
}

// ─── LoRa Signal Wave Rings ───
function LoRaSignalWaves({ origin, target, color = COLORS.cyan }) {
  const wavesRef = useRef([]);
  const groupRef = useRef();
  const WAVE_COUNT = 5;

  useFrame(({ clock }) => {
    wavesRef.current.forEach((ring, i) => {
      if (!ring) return;
      const t = ((clock.elapsedTime * 0.6 + i * 0.4) % 2.0) / 2.0;
      const scale = 0.2 + t * 1.8;
      ring.scale.set(scale, scale, scale);
      ring.material.opacity = (1 - t) * 0.35;
    });
  });

  const midPoint = [
    (origin[0] + target[0]) / 2,
    Math.max(origin[1], target[1]) + 2.5,
    (origin[2] + target[2]) / 2,
  ];

  return (
    <group ref={groupRef} position={midPoint}>
      {Array.from({ length: WAVE_COUNT }).map((_, i) => (
        <mesh
          key={i}
          ref={(el) => (wavesRef.current[i] = el)}
          rotation={[Math.PI / 2, 0, 0]}
        >
          <ringGeometry args={[0.8, 0.85, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.3} side={THREE.DoubleSide} />
        </mesh>
      ))}
      {/* "433 MHz" label */}
      <Text
        position={[0, 0.6, 0]}
        fontSize={0.2}
        color={color}
        anchorX="center"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
      >
        LoRa 433MHz
      </Text>
    </group>
  );
}

// ─── Gateway ESP32 Node ───
function GatewayNode({ position }) {
  const ref = useRef();
  const antennaGlow = useRef();

  useFrame(({ clock }) => {
    if (antennaGlow.current) {
      antennaGlow.current.material.emissiveIntensity = 0.5 + Math.sin(clock.elapsedTime * 5) * 0.5;
    }
  });

  return (
    <group ref={ref} position={position}>
      {/* Gateway enclosure */}
      <mesh>
        <boxGeometry args={[0.8, 0.3, 0.5]} />
        <meshStandardMaterial color="#1e3a5f" emissive="#0a1f3d" emissiveIntensity={0.4} metalness={0.5} roughness={0.5} />
      </mesh>

      {/* Antenna tall */}
      <mesh position={[0.3, 0.6, 0]}>
        <cylinderGeometry args={[0.02, 0.02, 1.0, 8]} />
        <meshStandardMaterial color="#aaa" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Antenna tip glow */}
      <mesh ref={antennaGlow} position={[0.3, 1.15, 0]}>
        <sphereGeometry args={[0.06, 16, 16]} />
        <meshStandardMaterial color={COLORS.cyan} emissive={COLORS.cyan} emissiveIntensity={0.5} />
      </mesh>

      {/* WiFi symbol indicator */}
      <mesh position={[-0.25, 0.18, 0.26]}>
        <boxGeometry args={[0.08, 0.06, 0.01]} />
        <meshBasicMaterial color="#15803D" />
      </mesh>

      {/* Label */}
      <Text
        position={[0, -0.35, 0]}
        fontSize={0.16}
        color={COLORS.cyan}
        anchorX="center"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
      >
        GATEWAY_SURFACE_01
      </Text>
    </group>
  );
}

// ─── Floating Dust Particles ───
function DustParticles({ count = 600 }) {
  const ref = useRef();

  const particles = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 30;
      positions[i * 3 + 1] = Math.random() * 8;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 30;
      sizes[i] = Math.random() * 0.04 + 0.01;
    }
    return { positions, sizes };
  }, [count]);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const pos = ref.current.geometry.attributes.position;
    for (let i = 0; i < count; i++) {
      let y = pos.getY(i);
      y += Math.sin(clock.elapsedTime * 0.3 + i * 0.1) * 0.003;
      pos.setX(i, pos.getX(i) + Math.sin(clock.elapsedTime * 0.2 + i) * 0.001);
      if (y > 8) y = 0;
      pos.setY(i, y);
    }
    pos.needsUpdate = true;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={particles.positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color={COLORS.dust}
        size={0.06}
        transparent
        opacity={0.4}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

// ─── Animated Grid Floor ───
function IndustrialGrid() {
  const ref = useRef();

  useFrame(({ clock }) => {
    if (ref.current) {
      ref.current.material.opacity = 0.15 + Math.sin(clock.elapsedTime * 0.3) * 0.05;
    }
  });

  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
      <planeGeometry args={[50, 50]} />
      <meshBasicMaterial color={COLORS.grid} transparent opacity={0.15} wireframe />
    </mesh>
  );
}

// ─── Mine Shaft Support Pillars ───
function MinePillar({ position, height = 5 }) {
  return (
    <group position={position}>
      {/* Main pillar */}
      <mesh position={[0, height / 2, 0]}>
        <boxGeometry args={[0.3, height, 0.3]} />
        <meshStandardMaterial color="#3a3a4a" roughness={0.9} metalness={0.1} />
      </mesh>
      {/* Cross beam */}
      <mesh position={[0, height, 0]}>
        <boxGeometry args={[1.5, 0.15, 0.2]} />
        <meshStandardMaterial color="#4a4a5a" roughness={0.85} metalness={0.15} />
      </mesh>
      {/* Warning stripe */}
      <mesh position={[0, 1, 0.16]}>
        <planeGeometry args={[0.28, 0.4]} />
        <meshBasicMaterial color={COLORS.zoneB} transparent opacity={0.7} />
      </mesh>
    </group>
  );
}

// ─── Scroll-Driven Camera Controller ───
function CameraController({ scrollProgress }) {
  const { camera } = useThree();

  useFrame(() => {
    const t = scrollProgress;

    // Cinematic camera path: orbit + descend into mine
    let x, y, z, lookX, lookY, lookZ;

    if (t < 0.2) {
      // Scene 1: High aerial overview
      const p = t / 0.2;
      x = 18 - p * 4;
      y = 12 - p * 2;
      z = 18 - p * 4;
      lookX = 0; lookY = -1; lookZ = 0;
    } else if (t < 0.4) {
      // Scene 2: Orbit around rig
      const p = (t - 0.2) / 0.2;
      const angle = p * Math.PI * 0.8;
      x = Math.cos(angle) * 12;
      y = 8 - p * 2;
      z = Math.sin(angle) * 12;
      lookX = 0; lookY = -1; lookZ = 0;
    } else if (t < 0.65) {
      // Scene 3: Close-up on sensor nodes
      const p = (t - 0.4) / 0.25;
      x = -4 + p * 8;
      y = 3 - p * 0.5;
      z = 6 - p * 2;
      lookX = 0; lookY = 0; lookZ = 0;
    } else if (t < 0.85) {
      // Scene 4: LoRa transmission focus
      const p = (t - 0.65) / 0.2;
      x = 5 + p * 3;
      y = 5 + p * 1;
      z = 5 + p * 3;
      lookX = 2; lookY = 2; lookZ = -2;
    } else {
      // Scene 5: Full system overview (pull back)
      const p = (t - 0.85) / 0.15;
      x = 8 + p * 6;
      y = 6 + p * 5;
      z = 8 + p * 6;
      lookX = 0; lookY = 0; lookZ = 0;
    }

    // Smooth lerp camera
    camera.position.lerp(new THREE.Vector3(x, y, z), 0.04);
    const lookTarget = new THREE.Vector3(lookX, lookY, lookZ);
    const currentLook = new THREE.Vector3();
    camera.getWorldDirection(currentLook);
    camera.lookAt(lookTarget.lerp(camera.position.clone().add(currentLook.multiplyScalar(10)), 0.96));
    camera.lookAt(lookTarget);
  });

  return null;
}

// ─── Subsidence Animation ───
function SubsidenceDeformation({ scrollProgress }) {
  const meshRef = useRef();

  const geo = useMemo(() => {
    return new THREE.PlaneGeometry(12, 12, 60, 60);
  }, []);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const pos = meshRef.current.geometry.attributes.position;
    const deformAmount = Math.min(1, scrollProgress * 2.5) * 2.0;

    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const dist = Math.sqrt(x * x + y * y);
      const sinkage = Math.max(0, 1 - dist / 5) * deformAmount;
      const ripple = Math.sin(dist * 2 - clock.elapsedTime * 1.5) * 0.05 * deformAmount;
      pos.setZ(i, -sinkage + ripple);
    }
    pos.needsUpdate = true;
    meshRef.current.geometry.computeVertexNormals();
  });

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1, 0]} geometry={geo}>
      <meshStandardMaterial
        color="#2a1a0a"
        emissive={COLORS.zoneC}
        emissiveIntensity={scrollProgress > 0.5 ? 0.15 : 0.03}
        wireframe
        transparent
        opacity={0.5}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

// ─── Data Stream Lines (Sensor to Gateway) ───
function DataStreamLine({ start, end, color = COLORS.cyan }) {
  const ref = useRef();
  const lineGeo = useMemo(() => {
    const points = [];
    for (let i = 0; i <= 20; i++) {
      const t = i / 20;
      points.push(new THREE.Vector3(
        start[0] + (end[0] - start[0]) * t,
        start[1] + (end[1] - start[1]) * t + Math.sin(t * Math.PI) * 1.5,
        start[2] + (end[2] - start[2]) * t,
      ));
    }
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [start, end]);

  useFrame(({ clock }) => {
    if (ref.current) {
      ref.current.material.dashOffset = -clock.elapsedTime * 2;
    }
  });

  return (
    <line ref={ref} geometry={lineGeo}>
      <lineDashedMaterial
        color={color}
        dashSize={0.3}
        gapSize={0.15}
        transparent
        opacity={0.5}
        linewidth={1}
      />
    </line>
  );
}

// ─── Title HUD (3D) ───
function Title3D({ scrollProgress }) {
  const ref = useRef();

  useFrame(() => {
    if (ref.current) {
      ref.current.material.opacity = Math.max(0, 1 - scrollProgress * 4);
    }
  });

  return (
    <group position={[0, 7, 0]}>
      <Text
        ref={ref}
        fontSize={1.2}
        color="#ffffff"
        anchorX="center"
        anchorY="middle"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
        maxWidth={20}
        textAlign="center"
        fillOpacity={1}
      >
        {'COAL MINE MONITORING'}
      </Text>
      <Text
        position={[0, -1.3, 0]}
        fontSize={0.4}
        color={COLORS.cyan}
        anchorX="center"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
      >
        {'TEAM GRADIENT // SIH 2026'}
      </Text>
      <Text
        position={[0, -2, 0]}
        fontSize={0.25}
        color={COLORS.dust}
        anchorX="center"
        font="https://fonts.gstatic.com/s/jetbrainsmono/v18/tDbY2o-flEEny0FZhsfKu5WU4xD-IQ-PuZJJXxfpAO-Lfjq0s5G.woff2"
      >
        {'PREDICTIVE SUBSURFACE DEFORMATION MONITORING'}
      </Text>
    </group>
  );
}


// ================================================================
// MAIN SCENE COMPOSITION
// ================================================================
export function MineScene({ scrollProgress = 0 }) {
  return (
    <>
      {/* Ambient & Directional Lighting */}
      <ambientLight intensity={0.25} color="#4a6fa5" />
      <directionalLight position={[10, 15, 5]} intensity={0.6} color="#8ab4f8" castShadow />
      <directionalLight position={[-8, 10, -5]} intensity={0.3} color="#f8a84a" />
      <pointLight position={[0, 3, 0]} intensity={0.8} color={COLORS.cyan} distance={15} decay={2} />
      <pointLight position={[-5, 1, -3]} intensity={0.4} color={COLORS.zoneB} distance={10} decay={2} />
      <pointLight position={[4, 1, 3]} intensity={0.4} color={COLORS.zoneA} distance={10} decay={2} />

      {/* Stars / Ambient Sky */}
      <Stars radius={80} depth={60} count={3000} factor={3} saturation={0.1} fade speed={0.5} />

      {/* Camera Controller */}
      <CameraController scrollProgress={scrollProgress} />

      {/* Floating 3D Title */}
      <Title3D scrollProgress={scrollProgress} />

      {/* Terrain Layers */}
      <TerrainLayer yOffset={-0.5} color={COLORS.terrain} />
      <TerrainLayer yOffset={-3} color={COLORS.rock} opacity={0.4} wireframe />

      {/* Industrial Grid */}
      <IndustrialGrid />

      {/* Subsidence Deformation (animated by scroll) */}
      <SubsidenceDeformation scrollProgress={scrollProgress} />

      {/* Subsidence Zones */}
      <SubsidenceZone position={[-6, 0.1, -4]} radius={3} color={COLORS.zoneA} label="ZONE A — SAFE" pulseSpeed={0.8} />
      <SubsidenceZone position={[0, 0.1, 0]} radius={4} color={COLORS.zoneB} label="ZONE B — WARNING" pulseSpeed={1.5} />
      <SubsidenceZone position={[5, 0.1, 3]} radius={2.5} color={COLORS.zoneC} label="ZONE C — CRITICAL" pulseSpeed={3} />

      {/* Sensor Nodes */}
      <SensorNode position={[-6, 0.5, -4]} nodeId="NODE_01 (REF)" color={COLORS.zoneA} />
      <SensorNode position={[0, 0.3, 0]} nodeId="NODE_02 (MON)" color={COLORS.cyan} />
      <SensorNode position={[5, 0.4, 3]} nodeId="NODE_03" color={COLORS.zoneC} isActive={scrollProgress > 0.3} />

      {/* Gateway */}
      <GatewayNode position={[8, 3, -6]} />

      {/* LoRa Signal Waves */}
      <LoRaSignalWaves origin={[0, 0.3, 0]} target={[8, 3, -6]} color={COLORS.cyan} />
      <LoRaSignalWaves origin={[-6, 0.5, -4]} target={[8, 3, -6]} color={COLORS.zoneA} />

      {/* Data Stream Lines */}
      <DataStreamLine start={[-6, 0.5, -4]} end={[8, 3, -6]} color={COLORS.zoneA} />
      <DataStreamLine start={[0, 0.3, 0]} end={[8, 3, -6]} color={COLORS.cyan} />
      <DataStreamLine start={[5, 0.4, 3]} end={[8, 3, -6]} color={COLORS.zoneC} />

      {/* Mine Support Pillars */}
      <MinePillar position={[-8, 0, -8]} height={4} />
      <MinePillar position={[8, 0, -8]} height={4.5} />
      <MinePillar position={[-8, 0, 8]} height={3.5} />
      <MinePillar position={[8, 0, 8]} height={4} />
      <MinePillar position={[0, 0, -10]} height={5} />
      <MinePillar position={[0, 0, 10]} height={3} />

      {/* Dust Particles */}
      <DustParticles count={800} />

      {/* Fog */}
      <fog attach="fog" args={[COLORS.bg, 15, 50]} />
    </>
  );
}

export default MineScene;
