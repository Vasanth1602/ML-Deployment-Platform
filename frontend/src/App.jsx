import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Deploy from './pages/Deploy';
import Applications from './pages/Applications';
import Instances from './pages/Instances';
import { socket } from './services/socket';
import './styles/globals.css';

function App() {
  useEffect(() => {
    // Initialize WebSocket connection on app mount
    socket.connect();

    // Cleanup on unmount
    return () => {
      socket.disconnect();
    };
  }, []);

  return (
    <Router>
      <div className="dark min-h-screen bg-background text-foreground">
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <Sidebar />

          {/* Main Content Area */}
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Top Navbar */}
            <Navbar />

            {/* Page Content */}
            <main className="flex-1 overflow-y-auto scrollbar-thin p-6">
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/deploy" element={<Deploy />} />
                <Route path="/applications" element={<Applications />} />
                <Route path="/instances" element={<Instances />} />
              </Routes>
            </main>
          </div>
        </div>
      </div>
    </Router>
  );
}

export default App;
