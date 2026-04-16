import { JournalEntry } from '@/lib/fileSystem';
import { Clock, FilePlus, Trash, PenLine, Flame, ShieldCheck, Search, Database } from 'lucide-react';

const opIcons: Record<string, React.ReactNode> = {
  create: <FilePlus className="w-3 h-3" />,
  delete: <Trash className="w-3 h-3" />,
  write: <PenLine className="w-3 h-3" />,
  crash: <Flame className="w-3 h-3" />,
  recover: <ShieldCheck className="w-3 h-3" />,
  fsck: <Search className="w-3 h-3" />,
  cache: <Database className="w-3 h-3" />,
};

const opColors: Record<string, string> = {
  create: 'text-primary',
  delete: 'text-warning',
  write: 'text-info',
  crash: 'text-danger',
  recover: 'text-primary',
  fsck: 'text-info',
  cache: 'text-accent',
};

interface JournalLogProps {
  journal: JournalEntry[];
}

export default function JournalLog({ journal }: JournalLogProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground flex items-center gap-2">
        <Clock className="w-4 h-4" /> Journal
      </h3>
      <div className="rounded-lg border border-border bg-background p-2 max-h-40 overflow-y-auto space-y-0.5">
        {journal.length === 0 ? (
          <p className="text-[10px] text-muted-foreground text-center py-4">No journal entries</p>
        ) : (
          journal.map(entry => (
            <div key={entry.id}
              className={`flex items-start gap-1.5 text-[10px] py-1 px-1.5 rounded ${
                !entry.committed ? 'bg-danger/10 border border-danger/20' : 'hover:bg-secondary/30'
              } transition-colors`}>
              <span className={opColors[entry.operation]}>{opIcons[entry.operation]}</span>
              <div className="flex-1 min-w-0">
                <span className="font-mono font-medium">{entry.fileName}</span>
                <span className="text-muted-foreground ml-1">{entry.details}</span>
                {!entry.committed && <span className="ml-1 text-danger font-semibold">[UNCOMMITTED]</span>}
              </div>
              <span className="text-muted-foreground shrink-0">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
