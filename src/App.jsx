import React, { useState } from 'react';
import { TelemetryProvider } from './context/TelemetryContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { AuthModal } from './components/AuthModal';
import { LandingPage } from './pages/LandingPage';
import { DashboardPage } from './pages/DashboardPage';

function MainApp() {
  const { currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState('landing'); // 'landing' | 'dashboard'
  const [authModal, setAuthModal] = useState({ isOpen: false, tab: 'WORKER_LOGIN' });

  const handleOpenAuth = (tabName = 'WORKER_LOGIN') => {
    setAuthModal({ isOpen: true, tab: tabName });
  };

  const handleCloseAuth = () => {
    setAuthModal({ isOpen: false, tab: 'WORKER_LOGIN' });
  };

  const handleLoginSuccess = () => {
    setActiveTab('dashboard');
  };

  return (
    <div className="min-h-screen bg-[#0D1117] text-[#E6EDF3] flex flex-col font-mono selection:bg-[#30363D] selection:text-white">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenAuth={handleOpenAuth}
      />

      <main className="flex-1 w-full">
        {activeTab === 'landing' ? (
          <LandingPage onOpenAuth={handleOpenAuth} onOpenDashboard={() => setActiveTab('dashboard')} />
        ) : (
          <DashboardPage onBackToStory={() => setActiveTab('landing')} />
        )}
      </main>

      <Footer />

      {/* Login & Sign Up Popup Modal */}
      <AuthModal
        isOpen={authModal.isOpen}
        onClose={handleCloseAuth}
        initialTab={authModal.tab}
        onLoginSuccess={handleLoginSuccess}
      />
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <TelemetryProvider>
        <MainApp />
      </TelemetryProvider>
    </AuthProvider>
  );
}

export default App;
