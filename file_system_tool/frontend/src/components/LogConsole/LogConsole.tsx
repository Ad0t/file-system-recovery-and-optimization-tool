import React, { useEffect, useRef } from 'react';
import { X, Download } from 'lucide-react';
import { useFileSystemStore } from '@/store/store';
import type { LogEntry } from '@/types';

export const LogConsole: React.FC = () => {
  const { logs, clearLogs } = useFileSystemStore();
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const exportLogs = () => {
    const logText = logs
      .map((log) => `[${log.timestamp}] [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n');

    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs-${new Date().toISOString()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-2">
      {/* Controls */}
      <div className="flex justify-between items-center">
        <div className="text-sm text-gray-600">
          {logs.length} entries
        </div>
        <div className="flex space-x-2">
          <button
            onClick={exportLogs}
            className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded flex items-center space-x-1"
          >
            <Download className="w-3 h-3" />
            <span>Export</span>
          </button>
          <button
            onClick={clearLogs}
            className="px-3 py-1 text-sm bg-red-100 hover:bg-red-200 text-red-700 rounded flex items-center space-x-1"
          >
            <X className="w-3 h-3" />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {/* Log Display */}
      <div className="bg-gray-900 rounded-lg p-4 h-48 overflow-y-auto font-mono text-xs">
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">No logs yet</div>
        ) : (
          <div className="space-y-1">
            {logs.map((log, index) => (
              <LogLine key={index} log={log} />
            ))}
            <div ref={logEndRef} />
          </div>
        )}
      </div>
    </div>
  );
};

interface LogLineProps {
  log: LogEntry;
}

const LogLine: React.FC<LogLineProps> = ({ log }) => {
  const levelColors = {
    debug: 'text-gray-400',
    info: 'text-blue-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    success: 'text-green-400',
  };

  const levelColor = levelColors[log.level] || 'text-gray-400';
  const timestamp = new Date(log.timestamp).toLocaleTimeString();

  return (
    <div className="flex space-x-2">
      <span className="text-gray-500">{timestamp}</span>
      <span className={`font-semibold ${levelColor}`}>[{log.level.toUpperCase()}]</span>
      <span className="text-gray-300">{log.message}</span>
    </div>
  );
};
