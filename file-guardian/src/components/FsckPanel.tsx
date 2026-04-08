import { FsckResult } from '@/lib/fileSystem';
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

interface FsckPanelProps {
  result: FsckResult | null;
}

export default function FsckPanel({ result }: FsckPanelProps) {
  if (!result) {
    return (
      <div className="rounded-lg border border-border bg-background p-3 text-center">
        <p className="text-xs text-muted-foreground">Run fsck to check file system consistency</p>
      </div>
    );
  }

  const totalIssues = result.orphanedBlocks + result.brokenChains + result.inconsistencies;
  const isClean = totalIssues === 0;

  return (
    <div className={`rounded-lg border p-3 space-y-2 ${
      isClean ? 'border-primary/30 bg-primary/5' : 'border-warning/30 bg-warning/5'
    }`}>
      <div className="flex items-center gap-2">
        {isClean ? (
          <CheckCircle className="w-4 h-4 text-primary" />
        ) : (
          <AlertTriangle className="w-4 h-4 text-warning" />
        )}
        <span className="text-xs font-semibold">
          {isClean ? 'File System Clean' : `${totalIssues} Issues Found`}
          {result.repaired && ' (Repaired)'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-1.5 text-center">
        <div className="rounded bg-background p-1.5">
          <div className={`text-sm font-bold font-mono ${result.orphanedBlocks > 0 ? 'text-warning' : 'text-primary'}`}>
            {result.orphanedBlocks}
          </div>
          <div className="text-[9px] text-muted-foreground">Orphaned</div>
        </div>
        <div className="rounded bg-background p-1.5">
          <div className={`text-sm font-bold font-mono ${result.brokenChains > 0 ? 'text-danger' : 'text-primary'}`}>
            {result.brokenChains}
          </div>
          <div className="text-[9px] text-muted-foreground">Broken</div>
        </div>
        <div className="rounded bg-background p-1.5">
          <div className={`text-sm font-bold font-mono ${result.inconsistencies > 0 ? 'text-danger' : 'text-primary'}`}>
            {result.inconsistencies}
          </div>
          <div className="text-[9px] text-muted-foreground">Errors</div>
        </div>
      </div>

      <div className="space-y-0.5">
        {result.details.map((d, i) => (
          <div key={i} className="flex items-start gap-1.5 text-[10px]">
            {isClean ? (
              <CheckCircle className="w-3 h-3 text-primary shrink-0 mt-0.5" />
            ) : (
              <XCircle className="w-3 h-3 text-warning shrink-0 mt-0.5" />
            )}
            <span className="text-muted-foreground">{d}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
