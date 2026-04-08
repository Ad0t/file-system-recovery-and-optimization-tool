import { CacheStats } from '@/lib/cache';
import { Database, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { useState } from 'react';

interface CachePanelProps {
  stats: CacheStats;
  onSetSize: (size: number) => void;
  onClear: () => void;
}

export default function CachePanel({ stats, onSetSize, onClear }: CachePanelProps) {
  const [cacheSize, setCacheSize] = useState(stats.maxSize);

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground flex items-center gap-2">
        <Database className="w-4 h-4" /> Cache (LRU)
      </h3>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg border border-border bg-background p-2">
          <div className="text-lg font-bold font-mono text-primary">{stats.hits}</div>
          <div className="text-[10px] text-muted-foreground">Hits</div>
        </div>
        <div className="rounded-lg border border-border bg-background p-2">
          <div className="text-lg font-bold font-mono text-danger">{stats.misses}</div>
          <div className="text-[10px] text-muted-foreground">Misses</div>
        </div>
        <div className="rounded-lg border border-border bg-background p-2">
          <div className="text-lg font-bold font-mono text-info">{(stats.hitRate * 100).toFixed(0)}%</div>
          <div className="text-[10px] text-muted-foreground">Hit Rate</div>
        </div>
      </div>

      {/* Usage bar */}
      <div className="rounded-lg border border-border bg-background p-2">
        <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
          <span>Cache Usage</span>
          <span>{stats.currentSize}/{stats.maxSize} blocks</span>
        </div>
        <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
          <div className="bg-info transition-all duration-300 h-full rounded-full"
            style={{ width: `${stats.maxSize > 0 ? (stats.currentSize / stats.maxSize) * 100 : 0}%` }} />
        </div>
      </div>

      {/* Cache size control */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground w-20">Size: {cacheSize}B</span>
        <Slider value={[cacheSize]} min={4} max={64}
          onValueChange={v => { setCacheSize(v[0]); onSetSize(v[0]); }} className="flex-1" />
      </div>

      <Button size="sm" variant="outline" className="w-full h-7 text-xs" onClick={onClear}>
        <Trash2 className="w-3 h-3 mr-1" /> Clear Cache
      </Button>

      {/* Cache entries */}
      <div className="rounded-lg border border-border bg-background p-2 max-h-32 overflow-y-auto space-y-0.5">
        {stats.entries.length === 0 ? (
          <p className="text-[10px] text-muted-foreground text-center py-2">Cache empty</p>
        ) : stats.entries.map((e, i) => (
          <div key={`${e.fileId}-${i}`} className="flex items-center justify-between text-[10px] px-1.5 py-0.5 rounded hover:bg-secondary/30">
            <span className="font-mono text-foreground truncate">{e.fileName}</span>
            <span className="text-muted-foreground shrink-0 ml-2">{e.accessCount}× · {e.size}B</span>
          </div>
        ))}
      </div>
    </div>
  );
}
