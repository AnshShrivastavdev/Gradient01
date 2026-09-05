import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ADMIN_CREDENTIALS } from '../services/firebase';

export const AuthPage = ({ setActiveTab }) => {
  const { registerWorker, loginWorker, loginAdmin } = useAuth();

  const [activeTab, setAuthTab] = useState('WORKER_LOGIN'); // 'WORKER_LOGIN' | 'WORKER_REGISTER' | 'ADMIN_LOGIN'

  // Worker Form State (Mobile Number based)
  const [workerMobile, setWorkerMobile] = useState('');
  const [workerEmpId, setWorkerEmpId] = useState('');
  const [workerPassword, setWorkerPassword] = useState('');
  const [workerName, setWorkerName] = useState('');
  const [workerSector, setWorkerSector] = useState('Zone B Longwall Panel');

  // Admin Form State (Single Email + Password)
  const [adminEmail, setAdminEmail] = useState(ADMIN_CREDENTIALS.email);
  const [adminPassword, setAdminPassword] = useState(ADMIN_CREDENTIALS.password);

  // Status Feedback Messages
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(false);

  // Worker Login Handler
  const handleWorkerLogin = async (e) => {
    e.preventDefault();
    setFeedback(null);

    if (!workerMobile || !workerEmpId) {
      setFeedback({ type: 'ERROR', message: 'PLEASE ENTER BOTH MOBILE NUMBER AND EMPLOYEE ID.' });
      return;
    }

    setLoading(true);
    const res = await loginWorker({
      mobile: workerMobile,
      empId: workerEmpId,
      password: workerPassword,
    });
    setLoading(false);

    if (res.success) {
      if (setActiveTab) setActiveTab('dashboard');
    } else {
      setFeedback({
        type: 'ERROR',
        message: res.message,
      });
    }
  };

  // Worker Registration Handler
  const handleWorkerRegister = (e) => {
    e.preventDefault();
    setFeedback(null);

    if (!workerEmpId || !workerName || !workerMobile) {
      setFeedback({ type: 'ERROR', message: 'MANDATORY: Worker ID, Full Name, and Mobile Number are required.' });
      return;
    }

    registerWorker({
      empId: workerEmpId,
      name: workerName,
      mobile: workerMobile,
      sector: workerSector,
      password: workerPassword || 'worker123',
    });

    setFeedback({
      type: 'SUCCESS',
      message: `ENROLLED SUCCESSFULLY: Worker [${workerEmpId.toUpperCase()}] added to live digital muster. You can now log in.`,
    });

    setTimeout(() => {
      setAuthTab('WORKER_LOGIN');
    }, 1200);
  };

  // Admin Login Handler
  const handleAdminLogin = async (e) => {
    e.preventDefault();
    setFeedback(null);

    setLoading(true);
    const res = await loginAdmin(adminEmail, adminPassword);
    setLoading(false);

    if (res.success) {
      if (setActiveTab) setActiveTab('dashboard');
    } else {
      setFeedback({ type: 'ERROR', message: res.message });
    }
  };

  const fillDemoWorker = () => {
    setWorkerMobile('9876543210');
    setWorkerEmpId('EMP-8842');
    setWorkerPassword('worker123');
  };

  const fillAdminCredentials = () => {
    setAdminEmail(ADMIN_CREDENTIALS.email);
    setAdminPassword(ADMIN_CREDENTIALS.password);
  };

  return (
    <div className="min-h-[calc(100vh-140px)] bg-[#0D1117] text-[#E6EDF3] font-mono py-12 px-4 flex items-center justify-center">
      <div className="max-w-xl w-full bg-[#161B22] border-2 border-[#30363D] p-6 md:p-8 space-y-6 shadow-2xl">
        {/* Header Title */}
        <div className="border-b border-[#30363D] pb-4 space-y-1 text-center">
          <div className="flex justify-center items-center space-x-2">
            <span className="inline-block bg-[#00B4D8] text-black px-2.5 py-0.5 text-xs font-bold uppercase">
              FIREBASE AUTHENTICATION
            </span>
            <span className="inline-block bg-[#15803D] text-white px-2.5 py-0.5 text-xs font-bold uppercase">
              DIGITAL SHIFT MUSTER
            </span>
          </div>
          <h2 className="text-xl md:text-2xl font-display font-extrabold text-white uppercase">
            UNDERGROUND COAL MINE ACCESS PORTAL
          </h2>
          <p className="text-xs text-[#8B949E]">
            Mobile-Verified Worker Check-in & Single-Admin SCADA Command Protocol
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="grid grid-cols-3 gap-2 bg-[#0D1117] p-1.5 border border-[#30363D] text-xs font-bold text-center">
          <button
            onClick={() => { setAuthTab('WORKER_LOGIN'); setFeedback(null); }}
            className={`py-2 border transition-colors ${
              activeTab === 'WORKER_LOGIN'
                ? 'bg-[#15803D] text-white border-white'
                : 'text-[#8B949E] border-transparent hover:text-white'
            }`}
          >
            [ WORKER LOGIN ]
          </button>
          <button
            onClick={() => { setAuthTab('WORKER_REGISTER'); setFeedback(null); }}
            className={`py-2 border transition-colors ${
              activeTab === 'WORKER_REGISTER'
                ? 'bg-[#00B4D8] text-black border-white'
                : 'text-[#8B949E] border-transparent hover:text-white'
            }`}
          >
            [ NEW WORKER ]
          </button>
          <button
            onClick={() => { setAuthTab('ADMIN_LOGIN'); setFeedback(null); }}
            className={`py-2 border transition-colors ${
              activeTab === 'ADMIN_LOGIN'
                ? 'bg-[#B45309] text-white border-white'
                : 'text-[#8B949E] border-transparent hover:text-white'
            }`}
          >
            [ ADMIN ONLY ]
          </button>
        </div>

        {/* Feedback Messages */}
        {feedback && (
          <div
            className={`p-3 text-xs border font-bold ${
              feedback.type === 'ERROR'
                ? 'bg-[#2A1215] border-[#B91C1C] text-[#EF4444]'
                : 'bg-[#0F291E] border-[#15803D] text-[#10B981]'
            }`}
          >
            {feedback.message}
          </div>
        )}

        {/* 1. WORKER LOGIN (Mobile Number + Employee ID) */}
        {activeTab === 'WORKER_LOGIN' && (
          <form onSubmit={handleWorkerLogin} className="space-y-4 text-xs">
            <div className="flex justify-between items-center text-[10px] text-[#8B949E]">
              <span>AUTHENTICATE WITH 10-DIGIT MOBILE NUMBER</span>
              <button
                type="button"
                onClick={fillDemoWorker}
                className="text-[#00B4D8] hover:underline"
              >
                [ AUTO-FILL DEMO WORKER ]
              </button>
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">10-Digit Mobile Number:</label>
              <div className="flex">
                <span className="bg-[#0D1117] border border-r-0 border-[#30363D] px-3 py-2 text-[#8B949E]">
                  +91
                </span>
                <input
                  type="tel"
                  maxLength="10"
                  value={workerMobile}
                  onChange={(e) => setWorkerMobile(e.target.value)}
                  placeholder="98765 43210"
                  className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#15803D]"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Worker Employee ID:</label>
              <input
                type="text"
                value={workerEmpId}
                onChange={(e) => setWorkerEmpId(e.target.value)}
                placeholder="EMP-8842"
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#15803D]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Shift PIN / Password:</label>
              <input
                type="password"
                value={workerPassword}
                onChange={(e) => setWorkerPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#15803D]"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#15803D] text-white font-bold uppercase border border-white hover:bg-green-700 transition-colors"
            >
              {loading ? '[ VERIFYING DIGITAL AUTH... ]' : '[ CHECK-IN TO UNDERGROUND SHIFT ]'}
            </button>
          </form>
        )}

        {/* 2. WORKER REGISTRATION */}
        {activeTab === 'WORKER_REGISTER' && (
          <form onSubmit={handleWorkerRegister} className="space-y-3.5 text-xs">
            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Worker Full Name:</label>
              <input
                type="text"
                value={workerName}
                onChange={(e) => setWorkerName(e.target.value)}
                placeholder="e.g. Rajesh Kumar"
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#00B4D8]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[#8B949E] uppercase font-bold">Employee ID:</label>
                <input
                  type="text"
                  value={workerEmpId}
                  onChange={(e) => setWorkerEmpId(e.target.value)}
                  placeholder="EMP-5521"
                  className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#00B4D8]"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[#8B949E] uppercase font-bold">Mobile Number:</label>
                <input
                  type="tel"
                  maxLength="10"
                  value={workerMobile}
                  onChange={(e) => setWorkerMobile(e.target.value)}
                  placeholder="9876543210"
                  className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#00B4D8]"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Assigned Mining Sector / Tunnel:</label>
              <select
                value={workerSector}
                onChange={(e) => setWorkerSector(e.target.value)}
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#00B4D8]"
              >
                <option value="Zone B Longwall Panel">Zone B Longwall Panel</option>
                <option value="Shaft #3 Roof Support">Shaft #3 Roof Support</option>
                <option value="Zone C Extraction Void">Zone C Extraction Void (High Hazard)</option>
                <option value="Main Airway Haulage Road">Main Airway Haulage Road</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Shift PIN / Password:</label>
              <input
                type="password"
                value={workerPassword}
                onChange={(e) => setWorkerPassword(e.target.value)}
                placeholder="Create shift PIN"
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#00B4D8]"
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-[#00B4D8] text-black font-bold uppercase border border-white hover:bg-cyan-400 transition-colors"
            >
              [ ENROLL IN DIGITAL SHIFT MUSTER ]
            </button>
          </form>
        )}

        {/* 3. ADMIN LOGIN (Single Dedicated Email + Password) */}
        {activeTab === 'ADMIN_LOGIN' && (
          <form onSubmit={handleAdminLogin} className="space-y-4 text-xs">
            <div className="p-3 bg-[#2A1D0E] border border-[#B45309] text-[#F59E0B] text-xs space-y-1">
              <div className="font-bold uppercase">⚠️ RESTRICTED SAFETY INCHARGE ACCESS</div>
              <p className="text-[11px] text-[#8B949E]">
                Single Authorized Admin Email Policy. Only the designated SCADA Safety Officer is authorized for Admin controls.
              </p>
            </div>

            <div className="flex justify-between items-center text-[10px]">
              <span className="text-[#8B949E]">DESIGNATED ADMIN EMAIL:</span>
              <button
                type="button"
                onClick={fillAdminCredentials}
                className="text-[#00B4D8] hover:underline"
              >
                [ AUTO-FILL ADMIN CREDENTIALS ]
              </button>
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Admin Email ID:</label>
              <input
                type="email"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                placeholder="admin@coalmine.gov.in"
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#B45309]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[#8B949E] uppercase font-bold">Admin Master Password:</label>
              <input
                type="password"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-[#0D1117] border border-[#30363D] p-2.5 text-white outline-none focus:border-[#B45309]"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#B45309] text-white font-bold uppercase border border-white hover:bg-amber-700 transition-colors"
            >
              {loading ? '[ AUTHENTICATING VIA FIREBASE... ]' : '[ ACCESS SCADA COMMAND CONSOLE ]'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
