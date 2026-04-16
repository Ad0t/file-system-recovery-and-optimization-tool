/**
 * useFileSystem.ts — Backend-driven file system hook.
 *
 * Replaces the old client-side simulation with API calls to the FastAPI backend.
 * Maintains the exact same return type so all UI components continue working unchanged.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import {
  DiskBlock, FileEntry, DirectoryEntry, JournalEntry, FsckResult,
  AllocationStrategy, FreeSpaceStrategy, CrashType, DiskStats,
} from '@/lib/fileSystem';
import { CacheStats } from '@/lib/cache';
import { BenchmarkResult, BenchmarkHistory, runBenchmark, calculateBenchmarkHistory } from '@/lib/benchmark';
import {
  fetchState, apiCreateFile, apiCreateDirectory, apiDeleteFile,
  apiCrashDisk, apiRecover, apiDefragment, apiFsck,
  apiSetCacheSize, apiClearCache, apiSetCacheStrategy, apiSetAllocationMethod,
  apiSetAllocationStrategy, apiCreateFileWithPowerFail, apiReplayJournal, apiSystemReset, apiReadFileById,
  ApiState,
} from '@/lib/api';

/** Convert backend state snapshot to the shapes our components expect. */
function mapState(api: ApiState) {
  // Disk blocks - already in the right shape
  const disk: DiskBlock[] = api.disk;

  // Files map
  const files = new Map<string, FileEntry>();
  for (const [id, f] of Object.entries(api.files)) {
    files.set(id, f as FileEntry);
  }

  // Directories map
  const directories = new Map<string, DirectoryEntry>();
  for (const [id, d] of Object.entries(api.directories)) {
    directories.set(id, d as DirectoryEntry);
  }

  // Journal
  const journal: JournalEntry[] = api.journal as JournalEntry[];

  // Stats
  const stats: DiskStats = api.stats;

  // Cache stats
  const cacheStats: CacheStats = api.cacheStats as CacheStats;

  // Benchmark history
  const benchmarkHistory: BenchmarkHistory = api.benchmarkHistory as BenchmarkHistory;

  // Fsck result
  const lastFsckResult: FsckResult | null = api.lastFsckResult as FsckResult | null;

  return {
    disk, files, directories, journal, stats,
    cacheStats, benchmarkHistory, lastFsckResult,
    lastAction: api.lastAction || 'System ready',
  };
}

export function useFileSystem() {
  const [disk, setDisk] = useState<DiskBlock[]>([]);
  const [files, setFiles] = useState<Map<string, FileEntry>>(new Map());
  const [directories, setDirectories] = useState<Map<string, DirectoryEntry>>(() => {
    const m = new Map<string, DirectoryEntry>();
    m.set('root', { id: 'root', name: '/', parentId: null, children: [], path: '/' });
    return m;
  });
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [lastAction, setLastAction] = useState<string>('Connecting to backend...');
  const [stats, setStats] = useState<DiskStats>({
    totalBlocks: 1024, usedBlocks: 0, freeBlocks: 1020,
    corruptedBlocks: 0, fragmentation: 0, readSpeed: 5, writeSpeed: 7.5,
  });
  const [cacheStats, setCacheStats] = useState<CacheStats>({
    hits: 0, misses: 0, hitRate: 0, entries: [], maxSize: 64, currentSize: 0,
  });
  const [benchmarkResults, setBenchmarkResults] = useState<BenchmarkResult[]>([]);
  const [lastFsckResult, setLastFsckResult] = useState<FsckResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [simulateCrashOnNextWrite, setSimulateCrashOnNextWrite] = useState(false);

  type FileReadResult = {
    fileName: string;
    blocksRead: number[];
    hits: number;
    misses: number;
  };

  // Track the current allocation method for benchmarks
  const currentAllocMethod = useRef<AllocationStrategy>('contiguous');

  /** Refresh all state from backend */
  const refreshState = useCallback(async () => {
    try {
      const apiState = await fetchState();
      const mapped = mapState(apiState);
      setDisk(mapped.disk);
      setFiles(mapped.files);
      setDirectories(mapped.directories);
      setJournal(mapped.journal);
      setStats(mapped.stats);
      setCacheStats(mapped.cacheStats);
      if (mapped.lastFsckResult) setLastFsckResult(mapped.lastFsckResult);
      setLastAction(mapped.lastAction);
    } catch (err) {
      console.error('Failed to fetch state:', err);
      setLastAction(`Error: ${err instanceof Error ? err.message : 'Failed to connect to backend'}`);
    }
  }, []);

  // Load initial state from backend
  useEffect(() => {
    refreshState();
  }, [refreshState]);

  // ─── Action handlers ──────────────────────────────────────────

  const createFile = useCallback((
    name: string, size: number, parentDir: string = 'root',
    allocationStrategy: AllocationStrategy = 'contiguous',
    freeSpaceStrategy: FreeSpaceStrategy = 'first-fit'
  ): boolean => {
    setLoading(true);
    setLastAction(`Creating "${name}"...`);

    // Set allocation method if changed
    const setMethodAndCreate = async () => {
      try {
        // Map frontend strategy names to backend names
        const methodMap: Record<string, string> = {
          'contiguous': 'contiguous',
          'linked': 'linked',
          'indexed': 'indexed',
        };
        const strategyMap: Record<string, string> = {
          'first-fit': 'first_fit',
          'best-fit': 'best_fit',
          'worst-fit': 'worst_fit',
        };

        // Set allocation method on backend
        await apiSetAllocationMethod(methodMap[allocationStrategy] || 'contiguous');
        await apiSetAllocationStrategy(strategyMap[freeSpaceStrategy] || 'first_fit');

        // Build path — parent directories use frontend dir IDs but backend uses paths
        const parentPath = parentDir === 'root' ? '/' : '';
        const filePath = parentPath ? `/${name}` : `/${name}`;

        // Backend size is in bytes, frontend size is block count
        const sizeInBytes = size * 4096;

        const shouldSimulateCrash = simulateCrashOnNextWrite;
        if (shouldSimulateCrash) {
          setSimulateCrashOnNextWrite(false);
          await apiCreateFileWithPowerFail(filePath, sizeInBytes, 0.5);
        } else {
          await apiCreateFile(filePath, sizeInBytes);
        }

        currentAllocMethod.current = allocationStrategy;

        // Run a benchmark
        const bench = runBenchmark(size, 0, allocationStrategy);
        setBenchmarkResults(prev => [bench, ...prev].slice(0, 100));

        await refreshState();
        setLastAction(
          shouldSimulateCrash
            ? `Created "${name}" with simulated power-fail during write`
            : `Created "${name}" (${size} blocks, ${allocationStrategy})`
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Failed to create "${name}": ${msg}`);
      } finally {
        setLoading(false);
      }
    };

    setMethodAndCreate();
    return true; // Optimistic — errors shown via lastAction
  }, [refreshState, simulateCrashOnNextWrite]);

  const deleteFile = useCallback((fileId: string) => {
    const file = files.get(fileId);
    if (!file) return;

    setLastAction(`Deleting "${file.name}"...`);

    (async () => {
      try {
        // We need to find the file path. Reconstruct from directory tree.
        const filePath = `/${file.name}`;
        await apiDeleteFile(filePath);
        await refreshState();
        setLastAction(`Deleted "${file.name}"`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Failed to delete "${file.name}": ${msg}`);
      }
    })();
  }, [files, refreshState]);

  const accessFile = useCallback(async (fileId: string): Promise<FileReadResult | null> => {
    const file = files.get(fileId);
    if (!file) return null;

    // Run a local benchmark for the access
    const bench = runBenchmark(file.size, file.fragmentation, file.allocationStrategy);
    setBenchmarkResults(prev => [bench, ...prev].slice(0, 100));

    try {
      const result = await apiReadFileById(fileId);
      const rawStats = result.cacheStats;
      setCacheStats({
        hits: rawStats.cache_hits,
        misses: rawStats.cache_misses,
        hitRate: rawStats.hit_rate,
        entries: [],
        maxSize: rawStats.max_cache_size,
        currentSize: rawStats.cache_size,
        evictions: rawStats.eviction_count,
        strategy: rawStats.strategy,
        mostAccessedBlocks: rawStats.most_accessed_blocks,
        cachedBlocks: rawStats.cached_blocks || [],
        accessFrequency: rawStats.access_frequency || {},
      });
      setLastAction(`Read "${file.name}" (${result.blocksRead.length} blocks)`);
      return {
        fileName: file.name,
        blocksRead: result.blocksRead,
        hits: rawStats.cache_hits,
        misses: rawStats.cache_misses,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setLastAction(`Read failed for "${file.name}": ${msg}`);
      return null;
    }
  }, [files]);

  const createDirectory = useCallback((name: string, parentDir: string = 'root') => {
    setLastAction(`Creating directory "${name}"...`);

    (async () => {
      try {
        const dirPath = `/${name}`;
        await apiCreateDirectory(dirPath);
        await refreshState();
        setLastAction(`Created directory "${name}"`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Failed to create directory: ${msg}`);
      }
    })();

    return 'pending';
  }, [refreshState]);

  const deleteDirectory = useCallback((dirId: string, recursive: boolean = false) => {
    const dir = directories.get(dirId);
    if (!dir || dirId === 'root') return;

    (async () => {
      try {
        await apiDeleteFile(dir.path, recursive);
        await refreshState();
        setLastAction(`Deleted directory "${dir.name}"`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Failed to delete directory: ${msg}`);
      }
    })();
  }, [directories, refreshState]);

  const crashDisk = useCallback((severity: number, crashType: CrashType = 'power-failure') => {
    setLastAction(`Simulating ${crashType}...`);

    (async () => {
      try {
        const result = await apiCrashDisk(severity, crashType);
        await refreshState();
        setLastAction(result.message || `${crashType}: crash simulated`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Crash simulation failed: ${msg}`);
      }
    })();
  }, [refreshState]);

  const recover = useCallback(() => {
    setLastAction('Recovering...');

    (async () => {
      try {
        const result = await apiRecover();
        await refreshState();
        setLastAction(result.message || 'Recovery complete');
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Recovery failed: ${msg}`);
      }
    })();
  }, [refreshState]);

  const defragment = useCallback(() => {
    setLastAction('Defragmenting...');

    (async () => {
      try {
        await apiDefragment();
        await refreshState();
        setLastAction('Disk defragmented successfully');
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Defragmentation failed: ${msg}`);
      }
    })();
  }, [refreshState]);

  const runFsck = useCallback((autoRepair: boolean = false) => {
    setLastAction('Running fsck...');

    (async () => {
      try {
        const result = await apiFsck(autoRepair, false);
        await refreshState();

        // Try to build FsckResult from backend response
        if (result) {
          const orphaned = ((result.blocks_marked_allocated_but_free as unknown[]) || []).length;
          const missing = ((result.blocks_marked_free_but_allocated as unknown[]) || []).length;
          const badInodes = ((result.orphaned_inodes as unknown[]) || []).length;
          const invalidDirs = ((result.invalid_directory_entries as unknown[]) || []).length;
          const corrupted = ((result.corrupted_blocks as unknown[]) || []).length;

          const detailsArr: string[] = [];
          if (orphaned > 0) detailsArr.push(`Found ${orphaned} leaked blocks`);
          if (missing > 0) detailsArr.push(`${missing} blocks missing in FSM`);
          if (badInodes > 0) detailsArr.push(`${badInodes} orphaned inodes`);
          if (corrupted > 0) detailsArr.push(`${corrupted} corrupted blocks detected`);
          if (invalidDirs > 0) detailsArr.push(`${invalidDirs} invalid directory entries`);
          if (detailsArr.length === 0) detailsArr.push('Check complete - no issues found');

          const fsckResult: FsckResult = {
            orphanedBlocks: orphaned,
            brokenChains: missing,
            inconsistencies: badInodes + invalidDirs + corrupted,
            repaired: autoRepair,
            details: detailsArr,
          };
          setLastFsckResult(fsckResult);
          setLastAction(`fsck complete: ${fsckResult.details.join(', ')}`);
        } else {
          setLastAction('fsck complete');
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`fsck failed: ${msg}`);
      }
    })();
  }, [refreshState]);

  const quarantineOrphans = useCallback(() => {
    setLastAction('Running fsck + quarantine to /lost+found...');
    (async () => {
      try {
        const result = await apiFsck(false, true);
        await refreshState();
        const quarantined = ((result.quarantined_files as unknown[]) || []).length;
        const backendMessage = typeof result.quarantine_message === 'string' ? result.quarantine_message : '';
        setLastAction(
          backendMessage || (
            quarantined > 0
              ? `Quarantined ${quarantined} orphaned chain(s) to /lost+found`
              : 'No orphaned chains found to quarantine'
          )
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Quarantine failed: ${msg}`);
      }
    })();
  }, [refreshState]);

  const replayJournal = useCallback(() => {
    setLastAction('Replaying journal for incomplete writes...');
    (async () => {
      try {
        const result = await apiReplayJournal();
        await refreshState();
        setLastAction(`Journal replay complete (${result.replayed_entries} replayed)`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setLastAction(`Journal replay failed: ${msg}`);
      }
    })();
  }, [refreshState]);

  const setCacheSize = useCallback((size: number) => {
    (async () => {
      try {
        await apiSetCacheSize(size);
        await refreshState();
      } catch (err) {
        console.error('Failed to set cache size:', err);
      }
    })();
  }, [refreshState]);

  const clearCache = useCallback(() => {
    (async () => {
      try {
        await apiClearCache();
        await refreshState();
        setLastAction('Cache cleared');
      } catch (err) {
        console.error('Failed to clear cache:', err);
      }
    })();
  }, [refreshState]);

  const setCacheStrategy = useCallback((strategy: 'LRU' | 'LFU') => {
    (async () => {
      try {
        await apiSetCacheStrategy(strategy);
        await refreshState();
        setLastAction(`Cache strategy: ${strategy}`);
      } catch (err) {
        console.error('Failed to set cache strategy:', err);
        setLastAction(`Cache strategy failed: ${err instanceof Error ? err.message : 'error'}`);
      }
    })();
  }, [refreshState]);

  const runIOBenchmark = useCallback((fileSize: number) => {
    // Benchmarks run client-side using the current fragmentation value
    const frag = stats.fragmentation;
    const strategies: AllocationStrategy[] = ['contiguous', 'linked', 'indexed'];
    const results = strategies.map(s => runBenchmark(fileSize, frag, s));
    setBenchmarkResults(prev => [...results, ...prev].slice(0, 100));
    setLastAction(`Benchmark complete: ${fileSize} block test`);
  }, [stats.fragmentation]);

  const factoryReset = useCallback(async (): Promise<boolean> => {
    setLoading(true);
    setLastAction('Factory reset in progress...');
    try {
      const result = await apiSystemReset();
      setBenchmarkResults([]);
      setLastFsckResult(null);
      await refreshState();
      setLastAction(result.message || 'File system factory reset complete.');
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setLastAction(`Factory reset failed: ${msg}`);
      return false;
    } finally {
      setLoading(false);
    }
  }, [refreshState]);

  const benchmarkHistory = calculateBenchmarkHistory(benchmarkResults);

  return {
    disk, files, directories, journal, stats, lastAction,
    lastFsckResult, cacheStats, benchmarkHistory, benchmarkResults,
    createFile, deleteFile, accessFile, createDirectory, deleteDirectory,
    crashDisk, recover, defragment, runFsck,
    quarantineOrphans, replayJournal,
    setCacheSize, clearCache, setCacheStrategy, runIOBenchmark, factoryReset,
    simulateCrashOnNextWrite, setSimulateCrashOnNextWrite,
  };
}
