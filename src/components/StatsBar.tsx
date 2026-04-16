import { DiskStats } from '@/lib/fileSystem';
import { HardDrive, Gauge, Zap, AlertTriangle } from 'lucide-react';

interface StatsBarProps {
  stats: DiskStats;
  lastAction: string;
}

export default function StatsBar({ stats, lastAction }: StatsBarProps) {
  const usagePercent = ((stats.usedBlocks / stats.totalBlocks) * 100).toFixed(1);
  const fragPercent = (stats.fragmentation * 100).toFixed(1);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          icon={<HardDrive className="w-4 h-4" />}
          label="Disk Usage"
          value={`${usagePercent}%`}
          sub={`${stats.usedBlocks}/${stats.totalBlocks} blocks`}
          color="text-primary"
        />
        <StatCard
          icon={<AlertTriangle className="w-4 h-4" />}
          label="Fragmentation"
          value={`${fragPercent}%`}
          sub={stats.corruptedBlocks > 0 ? `${stats.corruptedBlocks} corrupted` : 'Healthy'}
          color={stats.fragmentation > 0.5 ? 'text-danger' : stats.fragmentation > 0.2 ? 'text-warning' : 'text-primary'}
        />
        <StatCard
          icon={<Zap className="w-4 h-4" />}
          label="Read Speed"
          value={`${stats.readSpeed}ms`}
          sub="avg per block"
          color="text-info"
        />
        <StatCard
          icon={<Gauge className="w-4 h-4" />}
          label="Write Speed"
          value={`${stats.writeSpeed}ms`}
          sub="avg per block"
          color="text-info"
        />
      </div>

      {/* Usage bar */}
      <div className="rounded-lg border border-border bg-background p-3">
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span>Storage</span>
          <span>{stats.freeBlocks} blocks free</span>
        </div>
        <div className="h-2.5 bg-secondary rounded-full overflow-hidden flex">
          <div
            className="bg-primary transition-all duration-500 rounded-full"
            style={{ width: `${(stats.usedBlocks / stats.totalBlocks) * 100}%` }}
          />
          {stats.corruptedBlocks > 0 && (
            <div
              className="bg-danger transition-all duration-500"
              style={{ width: `${(stats.corruptedBlocks / stats.totalBlocks) * 100}%` }}
            />
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground font-mono">
        {'>'} {lastAction}
      </p>
    </div>
  );
}

function StatCard({ icon, label, value, sub, color }: {
  icon: React.ReactNode; label: string; value: string; sub: string; color: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className={`flex items-center gap-1.5 text-xs text-muted-foreground mb-1`}>
        <span className={color}>{icon}</span>
        {label}
      </div>
      <div className={`text-lg font-bold font-mono ${color}`}>{value}</div>
      <div className="text-xs text-muted-foreground">{sub}</div>
    </div>
  );
}
