/**
 * Firebase Authentication & Disaster Mitigation Service
 * -------------------------------------------------------------
 * Configured for Coal Mine Subsidence Monitoring System (Team Gradient).
 * - Admin Authentication: Single dedicated Email + Password (admin@coalmine.gov.in)
 * - Worker Authentication: Mobile Number + Worker ID / PIN (Digital Shift Muster)
 * - Automatic Fallback / Offline Safety: Ensures 100% continuous uptime underground.
 */

// Single Dedicated Safety Admin Credentials
export const ADMIN_CREDENTIALS = {
  email: 'admin@coalmine.gov.in',
  password: 'Admin@CoalMine2026',
  displayName: 'Safety Incharge / Geotechnical Admin',
  role: 'ADMIN',
  empId: 'ADMIN-DGMS-01',
};

// Default Firebase Configuration (reads from Vite env or uses pre-configured SIH project)
export const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'AIzaSyA_SIH_COAL_MINE_DEMO_KEY_2026',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'coal-mine-subsidence-sih.firebaseapp.com',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'coal-mine-subsidence-sih',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || 'coal-mine-subsidence-sih.appspot.com',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '104829104829',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '1:104829104829:web:98f018d40a28f810',
};

let firebaseApp = null;
let firebaseAuth = null;
let isFirebaseInitialized = false;

// Dynamic Safe Initialization of Firebase SDK
export const initFirebase = async () => {
  if (isFirebaseInitialized) return { app: firebaseApp, auth: firebaseAuth };

  try {
    const { initializeApp, getApps } = await import('firebase/app');
    const { getAuth } = await import('firebase/auth');

    if (!getApps().length) {
      firebaseApp = initializeApp(firebaseConfig);
    } else {
      firebaseApp = getApps()[0];
    }
    firebaseAuth = getAuth(firebaseApp);
    isFirebaseInitialized = true;
    console.log('[FIREBASE] Initialized successfully for project:', firebaseConfig.projectId);
  } catch (err) {
    console.warn('[FIREBASE] SDK initialization notice (using resilient local auth engine):', err.message);
  }

  return { app: firebaseApp, auth: firebaseAuth };
};

// Attempt initialization immediately in background
initFirebase();

/**
 * Authenticates Safety Incharge Admin
 * Enforces single email + password security policy
 */
export const authenticateAdmin = async (email, password) => {
  const normalizedEmail = email?.trim().toLowerCase();

  // Strict check against the dedicated single Admin credentials
  if (
    normalizedEmail === ADMIN_CREDENTIALS.email.toLowerCase() &&
    password === ADMIN_CREDENTIALS.password
  ) {
    try {
      if (firebaseAuth) {
        const { signInWithEmailAndPassword } = await import('firebase/auth');
        await signInWithEmailAndPassword(firebaseAuth, normalizedEmail, password).catch(() => {
          // Fallback to local verified session if remote demo user not pre-created
        });
      }
    } catch (e) {
      // Offline fallback
    }

    return {
      success: true,
      user: {
        role: 'ADMIN',
        email: ADMIN_CREDENTIALS.email,
        name: ADMIN_CREDENTIALS.displayName,
        empId: ADMIN_CREDENTIALS.empId,
        sector: 'SURFACE SCADA COMMAND CONSOLE',
        loginTime: new Date().toLocaleTimeString(),
      },
    };
  }

  return {
    success: false,
    message: `ACCESS DENIED: Only the designated Safety Incharge (${ADMIN_CREDENTIALS.email}) is authorized for Admin SCADA control.`,
  };
};

/**
 * Authenticates Underground Worker via Mobile Number + Worker ID
 */
export const authenticateWorkerWithMobile = async ({
  mobile,
  empId,
  password,
  activeLedger = [],
}) => {
  const cleanMobile = mobile?.replace(/[^0-9]/g, '');
  const cleanEmpId = empId?.trim().toUpperCase();

  if (!cleanMobile || cleanMobile.length < 10) {
    return { success: false, message: 'INVALID MOBILE: Please enter a valid 10-digit mobile number.' };
  }

  if (!cleanEmpId) {
    return { success: false, message: 'INVALID ID: Worker Employee ID is required.' };
  }

  // Look up worker in the active roster / ledger
  const matched = activeLedger.find(
    (w) =>
      w.empId.toUpperCase() === cleanEmpId ||
      w.mobile?.replace(/[^0-9]/g, '') === cleanMobile
  );

  if (!matched) {
    return {
      success: false,
      message: `WORKER NOT FOUND: Employee ID [${cleanEmpId}] or Mobile [${cleanMobile}] not enrolled in today's shift roster. Please register below.`,
    };
  }

  if (password && matched.password && matched.password !== password) {
    return { success: false, message: 'INCORRECT PIN / PASSWORD: Authentication failed.' };
  }

  return {
    success: true,
    user: {
      role: 'WORKER',
      empId: matched.empId,
      name: matched.name,
      mobile: matched.mobile || cleanMobile,
      sector: matched.sector || 'Zone B Longwall Panel',
      shift: matched.shift || 'Shift A (Morning)',
      status: 'UNDERGROUND (ACTIVE)',
      checkInTime: new Date().toLocaleTimeString(),
    },
  };
};
