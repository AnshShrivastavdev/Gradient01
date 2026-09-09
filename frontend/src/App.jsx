import React, { useState } from 'react';
import { WebSocketProvider } from './context/WebSocketContext';
import { useLiveTelemetry } from './hooks/useLiveTelemetry';
import { Navbar } from './components/Navbar';
import { AlertBanner } from './components/AlertBanner';
import { ZoneStatusGrid } from './components/ZoneStatusGrid';
import { SensorMetricCard } from './components/SensorMetricCard';
import { TimeSeriesChart } from './components/Charts/TimeSeriesChart';
import { VibrationFFTChart } from './components/Charts/VibrationFFTChart';
import { MineMapView } from './components/GISMap/MineMapView';
import DashboardView from './components/DashboardView';

const DashboardContent = () => {
  const [activeTab, setActiveTab] = useState('forecast'); // 'forecast' | 'stations'
  const [selectedNode, setSelectedNode] = useState('NODE_02');
  const { data: currentData } = useLiveTelemetry(selectedNode);

  return (
    <div className="min-h-screen bg-[#080C14] text-gray-100 flex flex-col font-sans">
      <Navbar />
      <AlertBanner />

      {/* Navigation Switcher between DashboardView (ML Forecaster) & Station Grid */}
      <div className="max-w-7xl w-full mx-auto px-6 pt-4 flex items-center justify-between">
        <div className="flex bg-[#0F1420] border border-gray-800 rounded-lg p-1 text-xs font-mono">
          <button
            onClick={() => setActiveTab('forecast')}
            className={`px-4 py-2 rounded-md font-bold transition-all ${
              activeTab === 'forecast'
                ? 'bg-blue-600 text-white shadow-md'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            ⚡ REAL-TIME ML FORECASTING HUD (DASHBOARDVIEW)
          </button>
          <button
            onClick={() => setActiveTab('stations')}
            className={`px-4 py-2 rounded-md font-bold transition-all ${
              activeTab === 'stations'
                ? 'bg-blue-600 text-white shadow-md'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            🗺️ FIELD STATIONS & GIS SENSORS
          </button>
        </div>
      </div>

      {activeTab === 'forecast' ? (
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
          <DashboardView />
        </main>
      ) : (
        <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
          {/* Top Zone Status Grid */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-mono uppercase tracking-widest text-gray-400">
                FIELD SECTOR OBSERVATION STATIONS (SELECT NODE TO INSPECT)
              </h2>
              <span className="text-xs font-mono text-blue-400">CURRENT FOCUS: {selectedNode}</span>
            </div>
            <ZoneStatusGrid selectedNode={selectedNode} onSelectNode={setSelectedNode} />
          </section>

          {/* Selected Sensor Metric Gauges */}
          <section>
            <SensorMetricCard data={currentData} />
          </section>

          {/* GIS Map & Real-time Charts */}
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <MineMapView selectedNode={selectedNode} onSelectNode={setSelectedNode} />
            <TimeSeriesChart currentData={currentData} />
          </section>

          {/* Vibration FFT Spectral Density */}
          <section>
            <VibrationFFTChart vibrationAmp={currentData.vibration_amp || 0.015} />
          </section>
        </main>
      )}

      <footer className="bg-[#0B0F19] border-t border-[#1F2937] py-4 text-center text-xs text-gray-500 font-mono">
        TEAM GRADIENT // SMART INDIA HACKATHON 2026 // IOT LORA SUBSIDENCE MONITORING
      </footer>
    </div>
  );
};

export default function App() {
  return (
    <WebSocketProvider>
      <DashboardContent />
    </WebSocketProvider>
  );
}
