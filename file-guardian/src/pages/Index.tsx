import { useState } from 'react';
import { motion } from 'framer-motion';
import { useFileSystem } from '@/hooks/useFileSystem';
import DiskMap from '@/components/DiskMap';
import DirectoryTree from '@/components/DirectoryTree';
import ControlPanel from '@/components/ControlPanel';
import StatsBar from '@/components/StatsBar';
import JournalLog from '@/components/JournalLog';
import CacheVisualizer from '@/components/CacheVisualizer';
import BenchmarkPanel from '@/components/BenchmarkPanel';
import FsckPanel from '@/components/FsckPanel';
import { Terminal } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

const Index = () => {
  const fs = useFileSystem();
  const { toast } = useToast();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const handleSelectFile = async (fileId: string) => {
    setSelectedFile(fileId);
    const readResult = await fs.accessFile(fileId);
    if (readResult) {
      toast({
        title: `Read ${readResult.fileName} (${readResult.blocksRead.length} Blocks)`,
        description: `Hits: ${readResult.hits}, Misses: ${readResult.misses}`,
      });
    }
  };

  const blockOwnerById: Record<number, string> = {};
  fs.disk.forEach((block) => {
    if (block.fileId) {
      const file = fs.files.get(block.fileId);
      blockOwnerById[block.id] = file?.name || block.fileId;
    }
  });

  return (
    <div className="min-h-screen bg-background scanline">
      <header className="border-b border-border px-6 py-3">
        <div className="max-w-[1600px] mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center glow-green">
            <Terminal className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-foreground">
              FS Recovery & Optimization Tool
            </h1>
            <p className="text-xs text-muted-foreground">
              FAT strategies • Free-space management • Crash recovery • Cache • Benchmarking
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto p-4 space-y-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          <StatsBar stats={fs.stats} lastAction={fs.lastAction} />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 }}
          className="rounded-xl border border-border bg-card p-4">
          <DiskMap disk={fs.disk} highlightFile={selectedFile} />
        </motion.div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.15 }}
            className="rounded-xl border border-border bg-card p-4">
            <ControlPanel
              onCreateFile={fs.createFile}
              onCreateDir={fs.createDirectory}
              onCrash={fs.crashDisk}
              onRecover={fs.recover}
              onReplayJournal={fs.replayJournal}
              onDefragment={fs.defragment}
              onFsck={fs.runFsck}
              onQuarantineOrphans={fs.quarantineOrphans}
              onBenchmark={fs.runIOBenchmark}
              onFactoryReset={fs.factoryReset}
              simulateCrashOnNextWrite={fs.simulateCrashOnNextWrite}
              onToggleSimulateCrashOnNextWrite={fs.setSimulateCrashOnNextWrite}
            />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.2 }}
            className="rounded-xl border border-border bg-card p-4 space-y-4">
            <DirectoryTree
              directories={fs.directories}
              files={fs.files}
              onSelectFile={handleSelectFile}
              onDeleteFile={fs.deleteFile}
              selectedFile={selectedFile}
            />
            <FsckPanel result={fs.lastFsckResult} />
            <JournalLog journal={fs.journal} />
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.25 }}
            className="rounded-xl border border-border bg-card p-4 space-y-4 lg:col-span-2">
            <CacheVisualizer
              stats={fs.cacheStats}
              onClearCache={fs.clearCache}
              onSetCacheSize={fs.setCacheSize}
              onSetCacheStrategy={fs.setCacheStrategy}
              blockOwnerById={blockOwnerById}
            />
            <BenchmarkPanel history={fs.benchmarkHistory} results={fs.benchmarkResults} />
          </motion.div>
        </div>
      </main>
    </div>
  );
};

export default Index;
