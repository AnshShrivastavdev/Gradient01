import React from 'react';
import { useTelemetry } from '../context/TelemetryContext';
import { useAuth } from '../context/AuthContext';

export const Navbar = ({ activeTab, setActiveTab, onOpenAuth }) => {
  const { telemetry } = useTelemetry();
  const { currentUser, logout } = useAuth();

  const getZoneBadgeColor = () => {
    if (telemetry.currentZone === 'ZONE_A') return 'bg-[#15803D] text-white';
    if (telemetry.currentZone === 'ZONE_B') return 'bg-[#B45309] text-white';
    return 'bg-[#B91C1C] text-white animate-pulse';
  };

  return (
    <header className="w-full bg-[#161B22] border-b border-[#30363D] sticky top-0 z-50 select-none">
      {/* Main Header Strip */}
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between gap-3 font-mono">
        <div
          onClick={() => setActiveTab('landing')}
          className="cursor-pointer flex items-center space-x-2"
        >
          <div className="w-3.5 h-3.5 bg-[#00B4D8] border border-white"></div>
          <h1 className="text-base md:text-lg font-display font-extrabold tracking-tight text-white uppercase">
            COAL MINE MONITORING SYSTEM
          </h1>
        </div>

        {/* Action Controls */}
        <nav className="flex items-center space-x-2 text-xs">
          <button
            onClick={() => setActiveTab('landing')}
            className={`px-3 py-1.5 border transition-colors ${
              activeTab === 'landing'
                ? 'bg-[#30363D] text-white border-white font-bold'
                : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
            }`}
          >
            [ 3D STORY ]
          </button>

          {currentUser ? (
            <>
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`px-3 py-1.5 border transition-colors ${
                  activeTab === 'dashboard'
                    ? 'bg-[#15803D] text-white border-white font-bold'
                    : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
                }`}
              >
                [ DASHBOARD ]
              </button>

              <button
                onClick={logout}
                className="px-2.5 py-1.5 bg-[#B91C1C] text-white border border-red-500 font-bold hover:bg-red-800"
              >
                [ LOGOUT ]
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => onOpenAuth('WORKER_LOGIN')}
                className="px-3 py-1.5 bg-[#15803D] text-white font-bold border border-white hover:bg-green-700 transition-colors"
              >
                [ LOG IN ]
              </button>

              <button
                onClick={() => onOpenAuth('WORKER_REGISTER')}
                className="px-3 py-1.5 bg-[#30363D] text-white font-bold border border-[#374151] hover:bg-[#374151] transition-colors"
              >
                [ SIGN UP ]
              </button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
};
