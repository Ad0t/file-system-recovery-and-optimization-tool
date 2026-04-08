/**
 * api.ts — Thin API client wrapping fetch() for all backend operations.
 *
 * Every function calls the FastAPI backend at /api/v1/*.
 * The Vite dev server proxies these to http://127.0.0.1:8000.
 */

const BASE = '/api/v1';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ─── State Snapshot ─────────────────────────────────────────────
export interface ApiState {
  disk: ApiDiskBlock[];
  files: Record<string, ApiFileEntry>;
  directories: Record<string, ApiDirectoryEntry>;
  journal: ApiJournalEntry[];
  stats: ApiDiskStats;
  cacheStats: ApiCacheStats;
  benchmarkHistory: ApiBenchmarkHistory;
  lastFsckResult: ApiFsckResult | null;
  lastAction: string;
}

export interface ApiDiskBlock {
  id: number;
  state: 'free' | 'used' | 'corrupted' | 'reserved' | 'journal';
  fileId: string | null;
  fragment: number;
  nextBlock: number | null;
}

export interface ApiFileEntry {
  id: string;
  name: string;
  size: number;
  blocks: number[];
  parentDir: string;
  isDirectory: boolean;
  createdAt: number;
  accessTime: number;
  fragmentation: number;
  allocationStrategy: 'contiguous' | 'linked' | 'indexed';
  indexBlock: number | null;
}

export interface ApiDirectoryEntry {
  id: string;
  name: string;
  parentId: string | null;
  children: string[];
  path: string;
}

export interface ApiJournalEntry {
  id: number;
  timestamp: number;
  operation: 'create' | 'delete' | 'write' | 'crash' | 'recover' | 'fsck' | 'cache';
  fileId: string;
  fileName: string;
  details: string;
  committed: boolean;
}

export interface ApiDiskStats {
  totalBlocks: number;
  usedBlocks: number;
  freeBlocks: number;
  corruptedBlocks: number;
  fragmentation: number;
  readSpeed: number;
  writeSpeed: number;
}

export interface ApiCacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  entries: { fileId: string; fileName: string; accessCount: number; lastAccess: number; size: number }[];
  maxSize: number;
  currentSize: number;
}

export interface ApiBenchmarkHistory {
  results: ApiBenchmarkResult[];
  avgReadTime: number;
  avgWriteTime: number;
  totalOps: number;
}

export interface ApiBenchmarkResult {
  fileSize: number;
  readTime: number;
  writeTime: number;
  readThroughput: number;
  writeThroughput: number;
  fragmentation: number;
  strategy: string;
  timestamp: number;
}

export interface ApiFsckResult {
  orphanedBlocks: number;
  brokenChains: number;
  inconsistencies: number;
  repaired: boolean;
  details: string[];
}

// ─── API Functions ──────────────────────────────────────────────

export const fetchState = () =>
  request<ApiState>('GET', '/state/snapshot');

export const apiCreateFile = (path: string, size: number) =>
  request<{ success: boolean }>('POST', '/fs/create', { path, size });

export const apiCreateDirectory = (path: string) =>
  request<{ success: boolean }>('POST', '/fs/mkdir', { path });

export const apiDeleteFile = (path: string, recursive = false) =>
  request<{ success: boolean }>('POST', '/fs/rm', { path, recursive });

export const apiCrashDisk = (severity: number, crash_type: string) =>
  request<{ success: boolean; message: string }>('POST', '/recovery/crash/simple', { severity, crash_type });

export const apiRecover = () =>
  request<{ success: boolean; message: string }>('POST', '/recovery/recover/simple');

export const apiDefragment = () =>
  request<{ success: boolean }>('POST', '/optimization/defrag/all', { strategy: 'sequential' });

export const apiFsck = (autoRepair = false) =>
  request<Record<string, unknown>>('POST', `/recovery/fsck?auto_repair=${autoRepair}`);

export const apiSetCacheSize = (new_size: number) =>
  request<{ success: boolean }>('POST', `/metrics/cache/resize?new_size=${new_size}`);

export const apiClearCache = () =>
  request<{ success: boolean }>('POST', '/metrics/cache/clear');

export const apiResetFs = () =>
  request<{ success: boolean }>('POST', '/fs/reset');

export const apiSetAllocationMethod = (method: string) =>
  request<{ success: boolean }>('POST', '/fs/fat/method', { method });

export const apiSetAllocationStrategy = (strategy: string) =>
  request<{ success: boolean }>('POST', '/disk/allocation/strategy', { strategy });

export const apiHealthCheck = () =>
  request<{ status: string }>('GET', '/../health');
