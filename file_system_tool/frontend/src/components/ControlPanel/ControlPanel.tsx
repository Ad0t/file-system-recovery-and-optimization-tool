import React, { useState } from 'react';
import { FileText, FolderPlus, Trash2, AlertTriangle, RefreshCw, Wrench, Gauge } from 'lucide-react';
import { apiClient } from '@/api/client';
import { useFileSystemStore, useAddLog } from '@/store/store';

export const ControlPanel: React.FC = () => {
  return (
    <div className="space-y-6">
      <FileOperations />
      <CrashSimulation />
      <RecoveryOperations />
      <OptimizationOperations />
    </div>
  );
};

const FileOperations: React.FC = () => {
  const [showCreateFile, setShowCreateFile] = useState(false);
  const [showCreateDir, setShowCreateDir] = useState(false);
  const addLog = useAddLog();

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center space-x-2">
        <FileText className="w-4 h-4" />
        <span>File Operations</span>
      </h3>

      <div className="space-y-2">
        <button
          onClick={() => setShowCreateFile(true)}
          className="w-full px-3 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded text-sm flex items-center justify-center space-x-2"
        >
          <FileText className="w-4 h-4" />
          <span>Create File</span>
        </button>

        <button
          onClick={() => setShowCreateDir(true)}
          className="w-full px-3 py-2 bg-green-500 hover:bg-green-600 text-white rounded text-sm flex items-center justify-center space-x-2"
        >
          <FolderPlus className="w-4 h-4" />
          <span>Create Directory</span>
        </button>
      </div>

      {showCreateFile && (
        <CreateFileDialog onClose={() => setShowCreateFile(false)} />
      )}

      {showCreateDir && (
        <CreateDirectoryDialog onClose={() => setShowCreateDir(false)} />
      )}
    </div>
  );
};

const CrashSimulation: React.FC = () => {
  const [crashType, setCrashType] = useState('power_failure');
  const [isInjecting, setIsInjecting] = useState(false);
  const addLog = useAddLog();

  const injectCrash = async () => {
    setIsInjecting(true);
    try {
      const response = await apiClient.injectCrash(crashType);
      addLog('warning', `Crash injected: ${response.data.crash_type}`);
    } catch (error) {
      addLog('error', 'Failed to inject crash');
    } finally {
      setIsInjecting(false);
    }
  };

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center space-x-2">
        <AlertTriangle className="w-4 h-4" />
        <span>Crash Simulation</span>
      </h3>

      <select
        value={crashType}
        onChange={(e) => setCrashType(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
      >
        <option value="power_failure">Power Failure</option>
        <option value="bit_corruption">Bit Corruption</option>
        <option value="metadata_corruption">Metadata Corruption</option>
        <option value="journal_corruption">Journal Corruption</option>
      </select>

      <button
        onClick={injectCrash}
        disabled={isInjecting}
        className="w-full px-3 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded text-sm disabled:opacity-50"
      >
        {isInjecting ? 'Injecting...' : 'Inject Crash'}
      </button>
    </div>
  );
};

const RecoveryOperations: React.FC = () => {
  const [isRecovering, setIsRecovering] = useState(false);
  const addLog = useAddLog();

  const recoverSystem = async () => {
    setIsRecovering(true);
    try {
      const response = await apiClient.recoverSystem();
      if (response.data.success) {
        addLog('success', `Recovery completed: ${response.data.recovered_transactions} transactions recovered`);
      } else {
        addLog('error', 'Recovery failed');
      }
    } catch (error) {
      addLog('error', 'Failed to recover system');
    } finally {
      setIsRecovering(false);
    }
  };

  const runFsck = async () => {
    try {
      const response = await apiClient.runFsck(true);
      if (response.data.is_consistent) {
        addLog('success', 'File system is consistent');
      } else {
        addLog('warning', `FSCK found ${response.data.issues_found.length} issues`);
      }
    } catch (error) {
      addLog('error', 'FSCK failed');
    }
  };

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center space-x-2">
        <RefreshCw className="w-4 h-4" />
        <span>Recovery</span>
      </h3>

      <button
        onClick={recoverSystem}
        disabled={isRecovering}
        className="w-full px-3 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded text-sm disabled:opacity-50"
      >
        {isRecovering ? 'Recovering...' : 'Recover System'}
      </button>

      <button
        onClick={runFsck}
        className="w-full px-3 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded text-sm"
      >
        Run FSCK
      </button>
    </div>
  );
};

const OptimizationOperations: React.FC = () => {
  const [isDefragging, setIsDefragging] = useState(false);
  const addLog = useAddLog();

  const defragment = async () => {
    setIsDefragging(true);
    try {
      const response = await apiClient.defragment();
      addLog('success', `Defragmentation completed: ${response.data.files_defragmented} files optimized`);
    } catch (error) {
      addLog('error', 'Defragmentation failed');
    } finally {
      setIsDefragging(false);
    }
  };

  const runBenchmark = async () => {
    try {
      addLog('info', 'Running benchmark...');
      const response = await apiClient.runBenchmark();
      addLog('success', 'Benchmark completed');
    } catch (error) {
      addLog('error', 'Benchmark failed');
    }
  };

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-700 flex items-center space-x-2">
        <Wrench className="w-4 h-4" />
        <span>Optimization</span>
      </h3>

      <button
        onClick={defragment}
        disabled={isDefragging}
        className="w-full px-3 py-2 bg-teal-500 hover:bg-teal-600 text-white rounded text-sm disabled:opacity-50"
      >
        {isDefragging ? 'Defragmenting...' : 'Defragment'}
      </button>

      <button
        onClick={runBenchmark}
        className="w-full px-3 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded text-sm"
      >
        <Gauge className="w-4 h-4 inline mr-2" />
        Run Benchmark
      </button>
    </div>
  );
};

// Dialogs

const CreateFileDialog: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [path, setPath] = useState('/');
  const [size, setSize] = useState(4096);
  const addLog = useAddLog();

  const handleCreate = async () => {
    try {
      await apiClient.createFile(path, size);
      addLog('success', `File created: ${path}`);
      onClose();
    } catch (error) {
      addLog('error', 'Failed to create file');
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">Create File</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Path
            </label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded"
              placeholder="/path/to/file.txt"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Size (bytes)
            </label>
            <input
              type="number"
              value={size}
              onChange={(e) => setSize(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded"
            />
          </div>
        </div>

        <div className="flex justify-end space-x-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
};

const CreateDirectoryDialog: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [path, setPath] = useState('/');
  const addLog = useAddLog();

  const handleCreate = async () => {
    try {
      await apiClient.createDirectory(path);
      addLog('success', `Directory created: ${path}`);
      onClose();
    } catch (error) {
      addLog('error', 'Failed to create directory');
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h3 className="text-lg font-semibold mb-4">Create Directory</h3>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Path
          </label>
          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded"
            placeholder="/path/to/directory"
          />
        </div>

        <div className="flex justify-end space-x-2 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
};
