// I/O Benchmarking for file system simulation

export interface BenchmarkResult {
  fileSize: number;
  readTime: number;   // ms
  writeTime: number;  // ms
  readThroughput: number;  // blocks/ms
  writeThroughput: number; // blocks/ms
  fragmentation: number;
  strategy: string;
  timestamp: number;
}

export interface BenchmarkHistory {
  results: BenchmarkResult[];
  avgReadTime: number;
  avgWriteTime: number;
  totalOps: number;
}

export function runBenchmark(
  fileSize: number,
  fragmentation: number,
  strategy: string
): BenchmarkResult {
  const baseRead = 2; // ms per block
  const baseWrite = 3;

  // Fragmentation penalty
  const fragPenalty = 1 + fragmentation * 4;

  // Strategy overhead
  const strategyOverhead = strategy === 'contiguous' ? 1 : strategy === 'linked' ? 1.3 : 1.15;

  // Size scaling (larger files slightly faster per-block due to sequential access)
  const sizeScaling = 1 + (1 / Math.max(fileSize, 1)) * 2;

  // Add jitter
  const jitter = () => 0.9 + Math.random() * 0.2;

  const readTime = baseRead * fileSize * fragPenalty * strategyOverhead * sizeScaling * jitter();
  const writeTime = baseWrite * fileSize * fragPenalty * strategyOverhead * sizeScaling * jitter();

  return {
    fileSize,
    readTime: Math.round(readTime * 100) / 100,
    writeTime: Math.round(writeTime * 100) / 100,
    readThroughput: Math.round((fileSize / readTime) * 1000) / 1000,
    writeThroughput: Math.round((fileSize / writeTime) * 1000) / 1000,
    fragmentation,
    strategy,
    timestamp: Date.now(),
  };
}

export function calculateBenchmarkHistory(results: BenchmarkResult[]): BenchmarkHistory {
  const avgRead = results.length > 0
    ? results.reduce((s, r) => s + r.readTime, 0) / results.length : 0;
  const avgWrite = results.length > 0
    ? results.reduce((s, r) => s + r.writeTime, 0) / results.length : 0;

  return {
    results,
    avgReadTime: Math.round(avgRead * 100) / 100,
    avgWriteTime: Math.round(avgWrite * 100) / 100,
    totalOps: results.length,
  };
}
