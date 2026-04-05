import React, { useEffect } from 'react';
import { MainLayout } from './components/Layout/MainLayout';
import { DirectoryTree } from './components/DirectoryTree/DirectoryTree';
import { DiskVisualizer } from './components/DiskVisualizer/DiskVisualizer';
import { PerformanceDashboard } from './components/PerformanceDashboard/PerformanceDashboard';
import { LogConsole } from './components/LogConsole/LogConsole';
import { ControlPanel } from './components/ControlPanel/ControlPanel';
import { useWebSocket } from './hooks/useWebSocket';
import { useFileSystemStore } from './store/store';
import { apiClient } from './api/client';

function App() {
  const { lastMessage } = useWebSocket();
  const { setCurrentMetrics, addLog } = useFileSystemStore();

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      console.log('WebSocket message:', lastMessage);

      switch (lastMessage.type) {
        case 'metrics_update':
          setCurrentMetrics(lastMessage.data);
          break;
        case 'file_created':
          addLog({
            timestamp: new Date().toISOString(),
            level: 'success',
            message: `File created: ${lastMessage.path}`,
          });
          break;
        case 'crash_injected':
          addLog({
            timestamp: new Date().toISOString(),
            level: 'warning',
            message: `Crash injected: ${lastMessage.crash_type}`,
          });
          break;
        // ... handle other message types
      }
    }
  }, [lastMessage]);

  // Load initial data
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      const [diskInfo, visualization] = await Promise.all([
        apiClient.getDiskInfo(),
        apiClient.getDiskVisualization(),
      ]);

      useFileSystemStore.getState().setDiskInfo(diskInfo.data);
      useFileSystemStore.getState().setDiskVisualization(visualization.data);
    } catch (error) {
      console.error('Failed to load initial data:', error);
    }
  };

  return (
    <MainLayout>
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Directory Tree & Controls */}
        <div className="col-span-3 space-y-6">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Directory Structure</h2>
            <DirectoryTree />
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Operations</h2>
            <ControlPanel />
          </div>
        </div>

        {/* Center Panel - Disk Visualization */}
        <div className="col-span-6">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Disk Blocks</h2>
            <DiskVisualizer />
          </div>
        </div>

        {/* Right Panel - Performance */}
        <div className="col-span-3">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Performance</h2>
            <PerformanceDashboard />
          </div>
        </div>

        {/* Bottom Panel - Logs */}
        <div className="col-span-12">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-4">Operation Log</h2>
            <LogConsole />
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

export default App;
