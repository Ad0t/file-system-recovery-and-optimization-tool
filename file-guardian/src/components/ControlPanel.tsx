import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import {
  FilePlus, FolderPlus, Skull, ShieldCheck, Layers, Zap, Search, Trash2
} from 'lucide-react';
import { AllocationStrategy, FreeSpaceStrategy, CrashType } from '@/lib/fileSystem';

interface ControlPanelProps {
  onCreateFile: (name: string, size: number, parentDir?: string, allocationStrategy?: AllocationStrategy, freeSpaceStrategy?: FreeSpaceStrategy) => boolean;
  onCreateDir: (name: string) => void;
  onCrash: (severity: number, crashType?: CrashType) => void;
  onRecover: () => void;
  onDefragment: () => void;
  onFsck: (autoRepair?: boolean) => void;
  onBenchmark: (fileSize: number) => void;
}

export default function ControlPanel({
  onCreateFile, onCreateDir, onCrash, onRecover, onDefragment, onFsck, onBenchmark,
}: ControlPanelProps) {
  const [fileName, setFileName] = useState('');
  const [fileSize, setFileSize] = useState(4);
  const [dirName, setDirName] = useState('');
  const [allocStrategy, setAllocStrategy] = useState<AllocationStrategy>('contiguous');
  const [freeStrategy, setFreeStrategy] = useState<FreeSpaceStrategy>('first-fit');
  const [crashSeverity, setCrashSeverity] = useState([0.3]);
  const [crashType, setCrashType] = useState<CrashType>('power-failure');
  const [benchSize, setBenchSize] = useState(8);

  const handleCreateFile = () => {
    if (!fileName.trim()) return;
    const success = onCreateFile(fileName.trim(), fileSize, 'root', allocStrategy, freeStrategy);
    if (success) { setFileName(''); setFileSize(4); }
  };

  const handleCreateDir = () => {
    if (!dirName.trim()) return;
    onCreateDir(dirName.trim());
    setDirName('');
  };

  const strategyBtns = (
    options: { value: string; label: string }[],
    current: string,
    onChange: (v: string) => void
  ) => (
    <div className="flex gap-1">
      {options.map(o => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
            current === o.value
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary text-muted-foreground hover:text-foreground'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground">
        Controls
      </h3>

      {/* Create File */}
      <div className="rounded-lg border border-border bg-card p-3 space-y-2">
        <p className="text-xs text-muted-foreground font-medium">Create File</p>
        <Input
          placeholder="filename.txt"
          value={fileName}
          onChange={e => setFileName(e.target.value)}
          className="h-7 text-xs bg-background"
          onKeyDown={e => e.key === 'Enter' && handleCreateFile()}
        />
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground w-16">Size: {fileSize}B</span>
          <Slider value={[fileSize]} min={1} max={32} onValueChange={v => setFileSize(v[0])} className="flex-1" />
        </div>
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground">FAT Strategy:</p>
          {strategyBtns([
            { value: 'contiguous', label: 'Contiguous' },
            { value: 'linked', label: 'Linked' },
            { value: 'indexed', label: 'Indexed' },
          ], allocStrategy, v => setAllocStrategy(v as AllocationStrategy))}
        </div>
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground">Free-Space:</p>
          {strategyBtns([
            { value: 'first-fit', label: 'First-Fit' },
            { value: 'best-fit', label: 'Best-Fit' },
            { value: 'worst-fit', label: 'Worst-Fit' },
          ], freeStrategy, v => setFreeStrategy(v as FreeSpaceStrategy))}
        </div>
        <Button size="sm" className="w-full h-7 text-xs" onClick={handleCreateFile}>
          <FilePlus className="w-3 h-3 mr-1" /> Create File
        </Button>
      </div>

      {/* Create Directory */}
      <div className="rounded-lg border border-border bg-card p-3 space-y-2">
        <p className="text-xs text-muted-foreground font-medium">Directory</p>
        <div className="flex gap-2">
          <Input placeholder="dirname" value={dirName} onChange={e => setDirName(e.target.value)}
            className="h-7 text-xs bg-background" onKeyDown={e => e.key === 'Enter' && handleCreateDir()} />
          <Button size="sm" className="h-7 shrink-0" onClick={handleCreateDir}>
            <FolderPlus className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Crash & Recovery */}
      <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 space-y-2">
        <p className="text-xs text-danger font-medium">Crash Simulation</p>
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground">Type:</p>
          {strategyBtns([
            { value: 'power-failure', label: 'Power' },
            { value: 'kernel-panic', label: 'Kernel' },
            { value: 'disk-error', label: 'Disk' },
          ], crashType, v => setCrashType(v as CrashType))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground w-20">Severity: {(crashSeverity[0] * 100).toFixed(0)}%</span>
          <Slider value={crashSeverity} min={0.1} max={0.8} step={0.05} onValueChange={setCrashSeverity} className="flex-1" />
        </div>
        <div className="flex gap-1.5">
          <Button size="sm" variant="destructive" className="flex-1 h-7 text-xs" onClick={() => onCrash(crashSeverity[0], crashType)}>
            <Skull className="w-3 h-3 mr-1" /> Crash
          </Button>
          <Button size="sm" variant="outline" className="flex-1 h-7 text-xs" onClick={onRecover}>
            <ShieldCheck className="w-3 h-3 mr-1" /> Recover
          </Button>
        </div>
      </div>

      {/* fsck */}
      <div className="rounded-lg border border-info/30 bg-info/5 p-3 space-y-2">
        <p className="text-xs text-info font-medium">File System Check</p>
        <div className="flex gap-1.5">
          <Button size="sm" variant="outline" className="flex-1 h-7 text-xs" onClick={() => onFsck(false)}>
            <Search className="w-3 h-3 mr-1" /> Scan
          </Button>
          <Button size="sm" variant="outline" className="flex-1 h-7 text-xs" onClick={() => onFsck(true)}>
            <Trash2 className="w-3 h-3 mr-1" /> Auto-Repair
          </Button>
        </div>
      </div>

      {/* Optimization */}
      <div className="flex gap-1.5">
        <Button size="sm" variant="outline" className="flex-1 h-7 text-xs" onClick={onDefragment}>
          <Layers className="w-3 h-3 mr-1" /> Defrag
        </Button>
        <Button size="sm" variant="outline" className="flex-1 h-7 text-xs" onClick={() => onBenchmark(benchSize)}>
          <Zap className="w-3 h-3 mr-1" /> Bench
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground w-20">Bench: {benchSize}B</span>
        <Slider value={[benchSize]} min={1} max={32} onValueChange={v => setBenchSize(v[0])} className="flex-1" />
      </div>
    </div>
  );
}
