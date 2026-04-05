import { create } from 'zustand';
import type {
  FileInfo,
  DiskInfo,
  DiskVisualization,
  PerformanceMetrics,
  LogEntry,
} from '@/types';

interface FileSystemState {
  // File System State
  currentPath: string;
  directoryListing: FileInfo[];
  diskInfo: DiskInfo | null;
  diskVisualization: DiskVisualization | null;
  selectedFile: FileInfo | null;

  // Performance State
  currentMetrics: PerformanceMetrics | null;
  metricsHistory: PerformanceMetrics[];

  // Logs
  logs: LogEntry[];

  // UI State
  isLoading: boolean;
  error: string | null;

  // Actions
  setCurrentPath: (path: string) => void;
  setDirectoryListing: (listing: FileInfo[]) => void;
  setDiskInfo: (info: DiskInfo) => void;
  setDiskVisualization: (viz: DiskVisualization) => void;
  setSelectedFile: (file: FileInfo | null) => void;
  setCurrentMetrics: (metrics: PerformanceMetrics) => void;
  addMetricsToHistory: (metrics: PerformanceMetrics) => void;
  addLog: (log: LogEntry) => void;
  clearLogs: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useFileSystemStore = create<FileSystemState>((set) => ({
  // Initial state
  currentPath: '/',
  directoryListing: [],
  diskInfo: null,
  diskVisualization: null,
  selectedFile: null,
  currentMetrics: null,
  metricsHistory: [],
  logs: [],
  isLoading: false,
  error: null,

  // Actions
  setCurrentPath: (path) => set({ currentPath: path }),

  setDirectoryListing: (listing) => set({ directoryListing: listing }),

  setDiskInfo: (info) => set({ diskInfo: info }),

  setDiskVisualization: (viz) => set({ diskVisualization: viz }),

  setSelectedFile: (file) => set({ selectedFile: file }),

  setCurrentMetrics: (metrics) => set({ currentMetrics: metrics }),

  addMetricsToHistory: (metrics) =>
    set((state) => ({
      metricsHistory: [...state.metricsHistory.slice(-50), metrics], // Keep last 50
    })),

  addLog: (log) =>
    set((state) => ({
      logs: [...state.logs, log],
    })),

  clearLogs: () => set({ logs: [] }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),
}));

// Helper hook to add logs
export const useAddLog = () => {
  const addLog = useFileSystemStore((state) => state.addLog);

  return (level: LogEntry['level'], message: string) => {
    addLog({
      timestamp: new Date().toISOString(),
      level,
      message,
    });
  };
};
