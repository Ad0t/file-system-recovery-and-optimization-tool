import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Activity, Gauge, RefreshCw, Trash2, TrendingDown, TrendingUp, Zap } from 'lucide-react';
import { CacheStats as LiveCacheStats } from '@/lib/cache';

type CacheAlgorithm = 'LRU' | 'LFU' | 'FIFO';

export type CacheBlock = {
  blockNum: number;
  freq: number;
  lastAccessed: number;
  isDirty: boolean;
};

const INITIAL_TARGET = 24;

function createInitialBlocks(size: number): CacheBlock[] {
  const now = Date.now();
  return Array.from({ length: Math.min(8, size) }, (_, idx) => ({
    blockNum: idx + 1,
    freq: Math.floor(Math.random() * 4) + 1,
    lastAccessed: now - idx * 1_000,
    isDirty: Math.random() > 0.7,
  }));
}

function getHeatColor(freq: number, maxFreq: number) {
  const normalized = maxFreq <= 1 ? 0 : (freq - 1) / (maxFreq - 1);
  const hue = 220 - normalized * 220; // blue -> red
  const saturation = 90;
  const lightness = 56 - normalized * 10;
  return `hsl(${hue} ${saturation}% ${lightness}%)`;
}

interface CacheVisualizerProps {
  stats: LiveCacheStats;
  onClearCache: () => void;
  onSetCacheSize: (size: number) => void;
  onSetCacheStrategy: (strategy: 'LRU' | 'LFU') => void;
  blockOwnerById: Record<number, string>;
}

function blockReadFrequency(freqMap: Record<string, number> | undefined, blockNum: number): number {
  if (!freqMap || typeof freqMap !== 'object') return 1;
  const a = freqMap[String(blockNum)];
  if (typeof a === 'number') return a;
  const b = (freqMap as unknown as Record<number, number>)[blockNum];
  return typeof b === 'number' ? b : 1;
}

export default function CacheVisualizer({
  stats,
  onClearCache,
  onSetCacheSize,
  onSetCacheStrategy,
  blockOwnerById,
}: CacheVisualizerProps) {
  const [algorithm, setAlgorithm] = useState<CacheAlgorithm>('LRU');
  const [cacheSizeSlider, setCacheSizeSlider] = useState(INITIAL_TARGET);
  const [cacheBlocks, setCacheBlocks] = useState<CacheBlock[]>(() => createInitialBlocks(INITIAL_TARGET));
  const [lastAccessedBlock, setLastAccessedBlock] = useState<number | null>(null);
  const [lastOutcome, setLastOutcome] = useState<'hit' | 'miss' | null>(null);

  const sortedBlocks = useMemo(() => {
    if (algorithm === 'LRU') {
      return [...cacheBlocks].sort((a, b) => b.lastAccessed - a.lastAccessed);
    }
    return [...cacheBlocks].sort((a, b) => b.freq - a.freq || b.lastAccessed - a.lastAccessed);
  }, [algorithm, cacheBlocks]);

  const groupedBlocks = useMemo(() => {
    const groups = new Map<string, CacheBlock[]>();
    for (const block of sortedBlocks) {
      const owner = blockOwnerById[block.blockNum] || 'Unknown / Unmapped';
      if (!groups.has(owner)) groups.set(owner, []);
      groups.get(owner)!.push(block);
    }
    const entries = Array.from(groups.entries());
    if (algorithm === 'LFU') {
      entries.sort((a, b) => {
        const maxA = Math.max(0, ...a[1].map((x) => x.freq));
        const maxB = Math.max(0, ...b[1].map((x) => x.freq));
        if (maxB !== maxA) return maxB - maxA;
        return a[0].localeCompare(b[0]);
      });
    }
    return entries;
  }, [sortedBlocks, blockOwnerById, algorithm]);

  const ringCircumference = 2 * Math.PI * 48;
  const ringOffset = ringCircumference - (stats.hitRate / 100) * ringCircumference;
  const maxFreq = Math.max(1, ...cacheBlocks.map((block) => block.freq));

  useEffect(() => {
    const backendBlocks = stats.cachedBlocks || [];
    const freqMap = stats.accessFrequency || {};
    const now = Date.now();
    const next = backendBlocks.map((blockNum, idx) => ({
      blockNum,
      freq: blockReadFrequency(freqMap, blockNum),
      lastAccessed: now - idx * 250,
      isDirty: false,
    }));
    setCacheBlocks(next);
  }, [stats.cachedBlocks, stats.accessFrequency]);

  useEffect(() => {
    const s = stats.strategy?.toUpperCase();
    if (s === 'LRU' || s === 'LFU') {
      setAlgorithm(s as CacheAlgorithm);
    }
  }, [stats.strategy]);

  useEffect(() => {
    if (stats.maxSize > 0) {
      setCacheSizeSlider(stats.maxSize);
    }
  }, [stats.maxSize]);

  const clearCache = () => {
    onClearCache();
    setCacheBlocks([]);
    setLastAccessedBlock(null);
    setLastOutcome(null);
  };

  const accessBlock = (selectedBlockNum?: number) => {
    if (selectedBlockNum == null) return;
    setLastAccessedBlock(selectedBlockNum);
    setLastOutcome('hit');
  };

  const handleTargetSizeChange = (newTarget: number) => {
    setCacheSizeSlider(newTarget);
    onSetCacheSize(newTarget);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground mb-2">
        Cache Manager
      </h3>
      <div className="rounded-xl border border-border bg-background p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1.1fr_auto_auto] md:items-end">
          <div className="space-y-1.5">
            <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">Cache Strategy</p>
            <Select
              value={algorithm}
              onValueChange={(value) => {
                const v = value as CacheAlgorithm;
                setAlgorithm(v);
                onSetCacheStrategy(v);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="LRU">Least Recently Used (LRU)</SelectItem>
                <SelectItem value="LFU">Least Frequently Used (LFU)</SelectItem>
                <SelectItem value="FIFO">First-In First-Out (FIFO)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
              <span>Cache Target Size</span>
              <span className="text-info">{cacheSizeSlider} blocks</span>
            </div>
            <Slider
              value={[cacheSizeSlider]}
              min={10}
              max={50}
              step={1}
              onValueChange={(value) => handleTargetSizeChange(value[0])}
            />
          </div>

          <Button
            variant="outline"
            className="bg-background"
            onClick={clearCache}
          >
            <Trash2 className="mr-2 h-4 w-4" /> Clear Cache
          </Button>

        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[220px_1fr]">
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
            <Gauge className="h-3.5 w-3.5 text-info" /> Telemetry
          </div>

          <div className="flex items-center justify-center">
            <div className="relative h-32 w-32">
              <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                <circle cx="60" cy="60" r="48" className="fill-none stroke-muted" strokeWidth="10" />
                <motion.circle
                  cx="60"
                  cy="60"
                  r="48"
                  className="fill-none stroke-info"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={ringCircumference}
                  animate={{ strokeDashoffset: ringOffset }}
                  transition={{ type: 'spring', stiffness: 120, damping: 20 }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-semibold text-foreground">{Math.round(stats.hitRate)}%</span>
                <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Hit Rate</span>
              </div>
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2">
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2.5">
              <p className="text-[10px] uppercase tracking-[0.16em] text-emerald-300">Hits</p>
              <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-emerald-200">
                <TrendingUp className="h-4 w-4" /> {stats.hits}
              </p>
            </div>
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5">
              <p className="text-[10px] uppercase tracking-[0.16em] text-rose-300">Misses</p>
              <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-rose-200">
                <TrendingDown className="h-4 w-4" /> {stats.misses}
              </p>
            </div>
            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-2.5">
              <p className="text-[10px] uppercase tracking-[0.16em] text-amber-300">Evictions</p>
              <p className="mt-1 flex items-center gap-2 text-lg font-semibold text-amber-200">
                <Zap className="h-4 w-4" /> {stats.evictions ?? 0}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-background p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <h3 className="text-xs uppercase tracking-[0.18em] text-muted-foreground">RAM / Cache Memory</h3>
              {algorithm === 'LFU' && (
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  LFU: order by read count (highest first); each chip shows block reads.
                </p>
              )}
            </div>
            <p className="shrink-0 text-xs text-muted-foreground">
              {stats.currentSize}/{stats.maxSize} blocks
            </p>
          </div>

          {cacheBlocks.length === 0 ? (
            <div className="flex h-60 items-center justify-center rounded-xl border border-dashed border-border bg-background text-muted-foreground">
              Cache empty. Trigger reads to populate memory.
            </div>
          ) : (
            <motion.div layout className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {groupedBlocks.map(([owner, blocks]) => (
                <div key={owner} className="rounded-lg border border-border bg-card p-2">
                  <p className="mb-1 truncate text-[11px] font-medium text-info">
                    {owner}
                    {algorithm === 'LFU' && blocks.length > 0 && (
                      <span className="ml-1.5 font-mono text-[10px] font-normal text-muted-foreground">
                        (max reads {Math.max(...blocks.map((b) => b.freq))})
                      </span>
                    )}
                  </p>
                  {algorithm === 'LRU' ? (
                    <div className="flex flex-wrap gap-1.5">
                      <AnimatePresence>
                        {blocks.map((block, idx) => (
                          <motion.button
                            key={block.blockNum}
                            layout
                            initial={{ opacity: 0, y: 12 }}
                            animate={{
                              opacity: Math.max(0.34, 1 - idx * 0.07),
                              y: 0,
                              scale: lastAccessedBlock === block.blockNum ? [1, 1.025, 1] : 1,
                            }}
                            exit={{ opacity: 0, x: 30, scale: 0.95 }}
                            transition={{ layout: { duration: 0.35 }, duration: 0.25 }}
                            onClick={() => accessBlock(block.blockNum)}
                            className="rounded-md border border-border bg-background px-2 py-1 text-left"
                          >
                            <p className="text-[11px] font-mono text-foreground">#{block.blockNum}</p>
                          </motion.button>
                        ))}
                      </AnimatePresence>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      <AnimatePresence>
                        {blocks.map((block) => (
                          <motion.button
                            key={block.blockNum}
                            layout
                            initial={{ opacity: 0, scale: 0.5 }}
                            animate={{
                              opacity: 1,
                              scale: lastAccessedBlock === block.blockNum ? [1, 1.08, 1] : 1,
                            }}
                            exit={{ opacity: 0, scale: 0.15, filter: 'blur(5px)' }}
                            transition={{ layout: { duration: 0.35 }, duration: 0.3 }}
                            onClick={() => accessBlock(block.blockNum)}
                            className="rounded-md border border-border px-2 py-1 text-left"
                            style={{ backgroundColor: getHeatColor(block.freq, maxFreq) }}
                          >
                            <p className="text-[11px] font-semibold text-slate-950 leading-tight">#{block.blockNum}</p>
                            <p className="text-[9px] font-mono font-semibold text-slate-900/90 leading-tight">
                              ×{block.freq} reads
                            </p>
                          </motion.button>
                        ))}
                      </AnimatePresence>
                    </div>
                  )}
                </div>
              ))}
            </motion.div>
          )}

          <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
            <Activity className="h-3.5 w-3.5" />
            {lastOutcome ? (
              <motion.span
                key={`${lastOutcome}-${lastAccessedBlock}`}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className={lastOutcome === 'hit' ? 'text-emerald-300' : 'text-rose-300'}
              >
                Last read: block #{lastAccessedBlock} ({lastOutcome.toUpperCase()})
              </motion.span>
            ) : (
              <span>No read events yet.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
