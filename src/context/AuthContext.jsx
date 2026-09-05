import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import {
  ADMIN_CREDENTIALS,
  authenticateAdmin,
  authenticateWorkerWithMobile,
} from '../services/firebase';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  // Currently authenticated profile: { role: 'ADMIN'|'WORKER', empId, name, mobile, sector, ... }
  const [currentUser, setCurrentUser] = useState({
    role: 'ADMIN',
    empId: ADMIN_CREDENTIALS.empId,
    name: ADMIN_CREDENTIALS.displayName,
    email: ADMIN_CREDENTIALS.email,
    sector: 'SURFACE SCADA COMMAND CONSOLE',
    loginTime: '06:00 AM IST',
  });

  // Digital Shift Muster & Safety Verification Roster (Replaces outdated physical paper registers)
  const [activeLedger, setActiveLedger] = useState([
    {
      empId: 'EMP-8842',
      name: 'Rajesh Kumar',
      mobile: '+91 98765 43210',
      sector: 'Zone B Longwall Panel',
      shift: 'Shift A (06:00 - 14:00)',
      status: 'UNDERGROUND (ACTIVE)',
      checkInTime: '06:15 AM IST',
      emergencyContact: '+91 98765 00001',
      password: 'worker123',
    },
    {
      empId: 'EMP-9104',
      name: 'Vikram Singh',
      mobile: '+91 98112 34567',
      sector: 'Shaft #3 Roof Support',
      shift: 'Shift A (06:00 - 14:00)',
      status: 'UNDERGROUND (ACTIVE)',
      checkInTime: '06:22 AM IST',
      emergencyContact: '+91 98112 00002',
      password: 'worker123',
    },
    {
      empId: 'EMP-7421',
      name: 'Amitabh Roy',
      mobile: '+91 97554 12389',
      sector: 'Zone C Extraction Void',
      shift: 'Shift A (06:00 - 14:00)',
      status: 'UNDERGROUND (ACTIVE)',
      checkInTime: '06:30 AM IST',
      emergencyContact: '+91 97554 00003',
      password: 'worker123',
    },
    {
      empId: 'EMP-6320',
      name: 'Sunil Soren',
      mobile: '+91 94321 87654',
      sector: 'Main Airway Haulage Road',
      shift: 'Shift A (06:00 - 14:00)',
      status: 'PENDING_VERIFICATION',
      checkInTime: '07:05 AM IST',
      emergencyContact: '+91 94321 00004',
      password: 'worker123',
    },
  ]);

  // Count of workers currently underground
  const undergroundCount = useMemo(() => {
    return activeLedger.filter((w) => w.status === 'UNDERGROUND (ACTIVE)').length;
  }, [activeLedger]);

  // Register a new worker with Mobile Number & Mining Sector
  const registerWorker = useCallback((workerData) => {
    const formattedMobile = workerData.mobile?.startsWith('+91')
      ? workerData.mobile
      : `+91 ${workerData.mobile?.replace(/[^0-9]/g, '').slice(-10)}`;

    const newRecord = {
      empId: workerData.empId.trim().toUpperCase(),
      name: workerData.name.trim(),
      mobile: formattedMobile,
      sector: workerData.sector || 'Zone B Longwall Panel',
      shift: workerData.shift || 'Shift A (06:00 - 14:00)',
      status: 'PENDING_VERIFICATION',
      checkInTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' IST',
      emergencyContact: workerData.emergencyContact || formattedMobile,
      password: workerData.password || 'worker123',
    };

    setActiveLedger((prev) => [newRecord, ...prev.filter((w) => w.empId !== newRecord.empId)]);
    return newRecord;
  }, []);

  // Worker Login using Mobile Number + Employee ID
  const loginWorker = useCallback(
    async (credentials) => {
      const { mobile, empId, password } = credentials;
      const res = await authenticateWorkerWithMobile({
        mobile,
        empId,
        password,
        activeLedger,
      });

      if (res.success) {
        // Mark worker status as active underground
        setActiveLedger((prev) =>
          prev.map((w) =>
            w.empId.toUpperCase() === res.user.empId.toUpperCase()
              ? {
                  ...w,
                  status: 'UNDERGROUND (ACTIVE)',
                  checkInTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' IST',
                }
              : w
          )
        );

        setCurrentUser({
          ...res.user,
          status: 'UNDERGROUND (ACTIVE)',
        });
        return { success: true, user: res.user };
      }

      return res;
    },
    [activeLedger]
  );

  // Admin Login enforcing the single dedicated Safety Incharge credentials
  const loginAdmin = useCallback(async (email, password) => {
    const res = await authenticateAdmin(email, password);
    if (res.success) {
      setCurrentUser(res.user);
      return { success: true, user: res.user };
    }
    return res;
  }, []);

  // Admin Muster Action: Approve worker shift clearance
  const approveWorker = useCallback((empId) => {
    setActiveLedger((prev) =>
      prev.map((w) => (w.empId === empId ? { ...w, status: 'UNDERGROUND (ACTIVE)' } : w))
    );
  }, []);

  // Admin Muster Action: Mark worker as safe on surface (checked out)
  const checkOutWorker = useCallback((empId) => {
    setActiveLedger((prev) =>
      prev.map((w) => (w.empId === empId ? { ...w, status: 'SURFACE (OFF-SHIFT)' } : w))
    );
  }, []);

  // Admin Muster Action: Flag or reject worker
  const rejectWorker = useCallback((empId) => {
    setActiveLedger((prev) =>
      prev.map((w) => (w.empId === empId ? { ...w, status: 'REJECTED' } : w))
    );
  }, []);

  const logout = useCallback(() => {
    setCurrentUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        setCurrentUser,
        activeLedger,
        undergroundCount,
        registerWorker,
        loginWorker,
        loginAdmin,
        approveWorker,
        checkOutWorker,
        rejectWorker,
        logout,
        ADMIN_CREDENTIALS,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
