import { BenchmarkResult, BenchmarkHistory } from '@/lib/benchmark';
import { Activity } from 'lucide-react';

interface BenchmarkPanelProps {
  history: BenchmarkHistory;
  results: BenchmarkResult[];
}

export default function BenchmarkPanel({ history, results }: BenchmarkPanelProps) {
  const recent = results.slice(0, 15);

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground flex items-center gap-2">
        <Activity className="w-4 h-4" /> I/O Benchmark
      </h3>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg border border-border bg-background p-2">
          <div className="text-lg font-bold font-mono text-primary">{history.avgReadTime}ms</div>
          <div className="text-[10px] text-muted-foreground">Avg Read</div>
        </div>
        <div className="rounded-lg border border-border bg-background p-2">
          <div className="text-lg font-bold font-mono text-warning">{history.avgWriteTime}ms</div>
          <div className="text-[10px] text-muted-foreground">Avg Write</div>
        </div>
        <div className="rounded-lg border border-border bg-background p-2">
          <div className="text-lg font-bold font-mono text-info">{history.totalOps}</div>
          <div className="text-[10px] text-muted-foreground">Total Ops</div>
        </div>
      </div>

      {/* Throughput chart - simple bar visualization */}
      <div className="rounded-lg border border-border bg-background p-2 max-h-48 overflow-y-auto space-y-1">
        {recent.length === 0 ? (
          <p className="text-[10px] text-muted-foreground text-center py-4">No benchmark data yet</p>
        ) : recent.map((r, i) => {
          const maxTime = Math.max(...recent.map(x => Math.max(x.readTime, x.writeTime)), 1);
          return (
            <div key={`${r.timestamp}-${i}`} className="space-y-0.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="font-mono text-muted-foreground">{r.fileSize}B · {r.strategy}</span>
                <span className="text-muted-foreground">R:{r.readTime}ms W:{r.writeTime}ms</span>
              </div>
              <div className="flex gap-0.5 h-1.5">
                <div className="bg-primary/60 rounded-full transition-all" style={{ width: `${(r.readTime / maxTime) * 100}%` }} />
                <div className="bg-warning/60 rounded-full transition-all" style={{ width: `${(r.writeTime / maxTime) * 100}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex gap-3 text-[10px] text-muted-foreground justify-center">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-primary/60" /> Read</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warning/60" /> Write</span>
      </div>
    </div>
  );
}
