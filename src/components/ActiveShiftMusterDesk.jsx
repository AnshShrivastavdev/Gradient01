import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

/**
 * ActiveShiftMusterDesk
 * -------------------------------------------------------------
 * Digital Real-Time Shift Muster & Personnel Safety Tracking Desk.
 * Replaces old physical paper registers with live digital mobile attendance,
 * showing all active workers currently deployed underground on the Admin Dashboard.
 */
export const ActiveShiftMusterDesk = () => {
  const {
    activeLedger,
    undergroundCount,
    approveWorker,
    checkOutWorker,
    rejectWorker,
    registerWorker,
  } = useAuth();

  const [filterSector, setFilterSector] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [toastMessage, setToastMessage] = useState(null);

  const filteredWorkers = activeLedger.filter((w) => {
    const matchesSector = filterSector === 'ALL' || w.sector.includes(filterSector);
    const matchesQuery =
      w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.empId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.mobile.includes(searchQuery);
    return matchesSector && matchesQuery;
  });

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleCall = (worker) => {
    showToast(`📞 INITIATING DUPLEX RADIO / PHONE LINK TO ${worker.name} (${worker.mobile})`);
    window.open(`tel:${worker.mobile.replace(/\s+/g, '')}`);
  };

  const handleSms = (worker) => {
    showToast(`📱 EMERGENCY SMS DISPATCHED TO ${worker.name} (${worker.mobile})`);
  };

  const handleSimulateNewCheckIn = () => {
    const randomId = `EMP-${Math.floor(1000 + Math.random() * 9000)}`;
    const names = ['Deepak Sharma', 'Ramesh Yadav', 'Karan Murmu', 'Subhash Kisku', 'Anand Verma'];
    const randomName = names[Math.floor(Math.random() * names.length)];
    const randomMobile = `+91 98${Math.floor(10000000 + Math.random() * 90000000)}`;
    const sectors = ['Zone B Longwall Panel', 'Shaft #3 Roof Support', 'Zone C Extraction Void'];
    const randomSector = sectors[Math.floor(Math.random() * sectors.length)];

    registerWorker({
      empId: randomId,
      name: randomName,
      mobile: randomMobile,
      sector: randomSector,
      shift: 'Shift A (06:00 - 14:00)',
      password: 'worker123',
    });

    showToast(`✅ NEW WORKER CHECK-IN DETECTED: ${randomName} (${randomId}) via Mobile ${randomMobile}`);
  };

  return (
    <div className="bg-[#161B22] border-2 border-[#30363D] p-4 sm:p-6 space-y-4 font-mono text-[#E6EDF3] select-none">
      {/* Toast alert banner */}
      {toastMessage && (
        <div className="p-2.5 bg-[#00B4D8] text-black font-bold text-xs flex justify-between items-center animate-pulse">
          <span>{toastMessage}</span>
          <button onClick={() => setToastMessage(null)} className="font-extrabold ml-2">✕</button>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b border-[#30363D] pb-3">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-[10px] bg-[#15803D] text-white font-bold px-2 py-0.5 uppercase tracking-wider">
              REAL-TIME DIGITAL MUSTER
            </span>
            <span className="text-[10px] bg-[#30363D] text-[#8B949E] px-2 py-0.5 font-bold uppercase">
              REPLACES PHYSICAL REGISTERS
            </span>
          </div>
          <h3 className="text-base sm:text-lg font-display font-extrabold text-white uppercase tracking-tight">
            ACTIVE UNDERGROUND WORKER MUSTER & SAFETY VERIFICATION DESK
          </h3>
          <p className="text-xs text-[#8B949E]">
            Live roster of workers logged in via mobile numbers. Surface Safety Incharge tracks personnel location, shift verification, and emergency dispatch.
          </p>
        </div>

        {/* Action button */}
        <button
          onClick={handleSimulateNewCheckIn}
          className="px-3 py-1.5 bg-[#0D1117] text-[#00B4D8] font-bold text-xs uppercase border border-[#00B4D8] hover:bg-[#00B4D8] hover:text-black transition-colors"
        >
          [ + SIMULATE WORKER MOBILE CHECK-IN ]
        </button>
      </div>

      {/* Summary KPI Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">TOTAL ENROLLED</div>
          <div className="text-xl font-bold text-white">{activeLedger.length} WORKERS</div>
          <div className="text-[10px] text-[#8B949E]">Shift A Active Roster</div>
        </div>

        <div className="bg-[#0D1117] border border-[#15803D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">CURRENTLY UNDERGROUND</div>
          <div className="text-xl font-bold text-[#10B981] animate-pulse">
            {undergroundCount} ACTIVE
          </div>
          <div className="text-[10px] text-[#10B981]">Mobile Verified & Tagged</div>
        </div>

        <div className="bg-[#0D1117] border border-[#B45309] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">PENDING VERIFICATION</div>
          <div className="text-xl font-bold text-[#F59E0B]">
            {activeLedger.filter((w) => w.status === 'PENDING_VERIFICATION').length}
          </div>
          <div className="text-[10px] text-[#8B949E]">Awaiting Shift Egress Approval</div>
        </div>

        <div className="bg-[#0D1117] border border-[#30363D] p-3 space-y-1">
          <div className="text-[#8B949E] text-[10px] uppercase font-bold">SURFACE / OFF-SHIFT</div>
          <div className="text-xl font-bold text-[#8B949E]">
            {activeLedger.filter((w) => w.status === 'SURFACE (OFF-SHIFT)').length}
          </div>
          <div className="text-[10px] text-[#8B949E]">Safely Egressed</div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[#8B949E] text-[11px] font-bold">FILTER SECTOR:</span>
          {['ALL', 'Zone B', 'Zone C', 'Shaft #3'].map((sec) => (
            <button
              key={sec}
              onClick={() => setFilterSector(sec)}
              className={`px-2.5 py-1 font-bold border transition-colors ${
                filterSector === sec
                  ? 'bg-[#00B4D8] text-black border-white'
                  : 'bg-[#0D1117] text-[#8B949E] border-[#30363D] hover:text-white'
              }`}
            >
              {sec.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="flex items-center">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search Name, ID, Mobile..."
            className="bg-[#0D1117] border border-[#30363D] px-2.5 py-1 text-xs text-white outline-none focus:border-[#00B4D8] w-full sm:w-56"
          />
        </div>
      </div>

      {/* Digital Shift Muster Table */}
      <div className="overflow-x-auto border border-[#30363D]">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-[#0D1117] text-[#8B949E] border-b border-[#30363D]">
              <th className="p-3">EMP ID</th>
              <th className="p-3">WORKER NAME</th>
              <th className="p-3">MOBILE NUMBER (DIGITAL ID)</th>
              <th className="p-3">MINING SECTOR / TUNNEL</th>
              <th className="p-3">CHECK-IN TIME</th>
              <th className="p-3">CURRENT STATUS</th>
              <th className="p-3 text-right">SAFETY ACTIONS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#30363D]">
            {filteredWorkers.length === 0 ? (
              <tr>
                <td colSpan="7" className="p-4 text-center text-[#8B949E]">
                  No workers matching filter query.
                </td>
              </tr>
            ) : (
              filteredWorkers.map((row) => (
                <tr key={row.empId} className="hover:bg-[#0D1117] transition-colors">
                  {/* EMP ID */}
                  <td className="p-3 font-bold text-white">{row.empId}</td>

                  {/* Worker Name */}
                  <td className="p-3 font-bold">{row.name}</td>

                  {/* Mobile Number */}
                  <td className="p-3">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-[#00B4D8] font-bold">{row.mobile}</span>
                      <button
                        onClick={() => handleCall(row)}
                        title="Call Mobile"
                        className="px-1.5 py-0.5 bg-[#161B22] border border-[#30363D] text-[10px] hover:border-[#10B981] hover:text-[#10B981]"
                      >
                        📞
                      </button>
                      <button
                        onClick={() => handleSms(row)}
                        title="Send SMS"
                        className="px-1.5 py-0.5 bg-[#161B22] border border-[#30363D] text-[10px] hover:border-[#00B4D8] hover:text-[#00B4D8]"
                      >
                        💬
                      </button>
                    </div>
                  </td>

                  {/* Sector */}
                  <td className="p-3 text-[#8B949E]">
                    <span className="bg-[#0D1117] px-2 py-0.5 border border-[#30363D] text-white">
                      {row.sector}
                    </span>
                  </td>

                  {/* Check-in Time */}
                  <td className="p-3 text-[#8B949E]">{row.checkInTime}</td>

                  {/* Status */}
                  <td className="p-3">
                    <span
                      className={`px-2 py-0.5 text-[10px] font-bold uppercase ${
                        row.status === 'UNDERGROUND (ACTIVE)'
                          ? 'bg-[#15803D] text-white'
                          : row.status === 'SURFACE (OFF-SHIFT)'
                          ? 'bg-[#30363D] text-[#8B949E]'
                          : row.status === 'REJECTED'
                          ? 'bg-[#B91C1C] text-white'
                          : 'bg-[#B45309] text-white animate-pulse'
                      }`}
                    >
                      {row.status}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="p-3 text-right space-x-1.5 whitespace-nowrap">
                    {row.status === 'PENDING_VERIFICATION' && (
                      <>
                        <button
                          onClick={() => approveWorker(row.empId)}
                          className="px-2 py-1 bg-[#15803D] text-white font-bold text-[10px] uppercase border border-white hover:bg-green-700"
                        >
                          [ APPROVE ]
                        </button>
                        <button
                          onClick={() => rejectWorker(row.empId)}
                          className="px-2 py-1 bg-[#B91C1C] text-white font-bold text-[10px] uppercase border border-white hover:bg-red-800"
                        >
                          [ REJECT ]
                        </button>
                      </>
                    )}

                    {row.status === 'UNDERGROUND (ACTIVE)' && (
                      <>
                        <button
                          onClick={() => handleSms(row)}
                          className="px-2 py-1 bg-[#B45309] text-white font-bold text-[10px] uppercase border border-white hover:bg-amber-700"
                        >
                          [ EVAC SMS ]
                        </button>
                        <button
                          onClick={() => checkOutWorker(row.empId)}
                          className="px-2 py-1 bg-[#0D1117] text-[#8B949E] font-bold text-[10px] uppercase border border-[#30363D] hover:text-white"
                        >
                          [ CHECK-OUT ]
                        </button>
                      </>
                    )}

                    {row.status === 'SURFACE (OFF-SHIFT)' && (
                      <button
                        onClick={() => approveWorker(row.empId)}
                        className="px-2 py-1 bg-[#0D1117] text-[#10B981] font-bold text-[10px] uppercase border border-[#15803D] hover:bg-[#15803D] hover:text-white"
                      >
                        [ RE-CHECK IN ]
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
