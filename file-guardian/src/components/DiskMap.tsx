import { DiskBlock } from '@/lib/fileSystem';
import { motion } from 'framer-motion';
import { useState } from 'react';

interface DiskMapProps {
  disk: DiskBlock[];
  highlightFile?: string | null;
}

// Ensure type knows about our new backend param
interface ExtendedDiskBlock extends DiskBlock {
  allocStrategy?: string;
}

const stateColors: Record<string, string> = {
  free: 'bg-secondary',
  used: 'bg-primary/70',
  corrupted: 'bg-danger',
  reserved: 'bg-warning/60',
  journal: 'bg-info/60',
};

export default function DiskMap({ disk, highlightFile }: DiskMapProps) {
  const [hoveredFileId, setHoveredFileId] = useState<string | null>(null);

  // Determine grid columns: 32 for 1024 blocks, 16 for smaller
  const cols = disk.length > 256 ? 32 : 16;
  const gridClass = cols === 32
    ? 'grid-cols-[repeat(32,minmax(0,1fr))]'
    : 'grid-cols-16';

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground">
          Disk Block Map
          <span className="ml-2 text-xs font-normal text-muted-foreground/60">
            ({disk.length} blocks)
          </span>
        </h3>
        <div className="flex gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-secondary" /> Free</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-primary/70" /> Used</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-danger" /> Corrupt</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-warning/60" /> Reserved</span>
        </div>
      </div>
      <div className={`grid ${gridClass} gap-[1px] p-3 rounded-lg bg-background border border-border`}>
        {disk.map((block) => {
          const isHighlighted = (highlightFile && block.fileId === highlightFile) || (hoveredFileId && block.fileId === hoveredFileId);
          return (
            <motion.div
              key={block.id}
              onMouseEnter={() => block.fileId ? setHoveredFileId(block.fileId) : null}
              onMouseLeave={() => setHoveredFileId(null)}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{
                scale: isHighlighted ? 1.3 : 1,
                opacity: 1,
              }}
              transition={{ duration: 0.1, delay: Math.min(block.id * 0.0005, 0.5) }}
              className={`relative flex items-center justify-center aspect-[4/1] w-full rounded-[1px] transition-all duration-200 ${stateColors[block.state]} ${
                isHighlighted ? 'ring-1 ring-foreground glow-green z-10' : ''
              } ${block.state === 'corrupted' ? 'animate-pulse' : ''}`}
              title={`Block ${block.id}: ${block.state}${block.fileId ? ` (${block.fileId})` : ''} - ${(block as ExtendedDiskBlock).allocStrategy || 'none'}`}
            >
              {/* Linked allocation pointer */}
              {(block as ExtendedDiskBlock).allocStrategy === 'linked' && block.state === 'used' && block.nextBlock !== null && (
                <div className="absolute -right-[3px] z-10 opacity-60">
                  <svg width="6" height="6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-foreground">
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </div>
              )}
              {/* Indexed allocation visual cue for the first block (index block representation) */}
              {(block as ExtendedDiskBlock).allocStrategy === 'indexed' && block.state === 'used' && block.fragment === 0 && (
                <div className="absolute inset-0 bg-secondary/40 border border-secondary" title="Index Block Indicator" />
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
