// File System Simulator Core Logic

export type BlockState = 'free' | 'used' | 'corrupted' | 'reserved' | 'journal';
export type AllocationStrategy = 'contiguous' | 'linked' | 'indexed';
export type FreeSpaceStrategy = 'first-fit' | 'best-fit' | 'worst-fit';
export type CrashType = 'power-failure' | 'kernel-panic' | 'disk-error';

export interface DiskBlock {
  id: number;
  state: BlockState;
  fileId: string | null;
  fragment: number;
  nextBlock: number | null; // for linked allocation
}

export interface FileEntry {
  id: string;
  name: string;
  size: number;
  blocks: number[];
  parentDir: string;
  isDirectory: boolean;
  createdAt: number;
  accessTime: number;
  fragmentation: number;
  allocationStrategy: AllocationStrategy;
  indexBlock: number | null; // for indexed allocation
}

export interface DirectoryEntry {
  id: string;
  name: string;
  parentId: string | null;
  children: string[];
  path: string;
}

export interface JournalEntry {
  id: number;
  timestamp: number;
  operation: 'create' | 'delete' | 'write' | 'crash' | 'recover' | 'fsck' | 'cache';
  fileId: string;
  fileName: string;
  details: string;
  committed: boolean;
}

export interface DiskStats {
  totalBlocks: number;
  usedBlocks: number;
  freeBlocks: number;
  corruptedBlocks: number;
  fragmentation: number;
  readSpeed: number;
  writeSpeed: number;
}

export interface FsckResult {
  orphanedBlocks: number;
  brokenChains: number;
  inconsistencies: number;
  repaired: boolean;
  details: string[];
}

export const TOTAL_BLOCKS = 256;

export function createInitialDisk(): DiskBlock[] {
  const blocks: DiskBlock[] = [];
  for (let i = 0; i < TOTAL_BLOCKS; i++) {
    blocks.push({
      id: i,
      state: i < 4 ? 'reserved' : 'free',
      fileId: null,
      fragment: 0,
      nextBlock: null,
    });
  }
  return blocks;
}

export function createRootDirectory(): DirectoryEntry {
  return { id: 'root', name: '/', parentId: null, children: [], path: '/' };
}

let fileCounter = 0;
let journalCounter = 0;

export function generateFileId(): string {
  return `file_${++fileCounter}_${Date.now()}`;
}

export function generateDirId(): string {
  return `dir_${++fileCounter}_${Date.now()}`;
}

// Free space bitmap
export function getBitmap(disk: DiskBlock[]): boolean[] {
  return disk.map(b => b.state === 'free');
}

// Free-space strategy implementations
function findFreeBlocks(disk: DiskBlock[], size: number, strategy: FreeSpaceStrategy): number[] {
  const bitmap = getBitmap(disk);

  // Find all free segments
  const segments: { start: number; length: number }[] = [];
  let segStart = -1;
  for (let i = 0; i < bitmap.length; i++) {
    if (bitmap[i]) {
      if (segStart === -1) segStart = i;
    } else {
      if (segStart !== -1) {
        segments.push({ start: segStart, length: i - segStart });
        segStart = -1;
      }
    }
  }
  if (segStart !== -1) segments.push({ start: segStart, length: bitmap.length - segStart });

  // Filter segments that can fit the size
  const viable = segments.filter(s => s.length >= size);
  if (viable.length === 0) {
    // Gather scattered free blocks
    const free: number[] = [];
    for (let i = 0; i < bitmap.length && free.length < size; i++) {
      if (bitmap[i]) free.push(i);
    }
    return free.length >= size ? free.slice(0, size) : [];
  }

  let chosen: { start: number; length: number };
  switch (strategy) {
    case 'first-fit':
      chosen = viable[0];
      break;
    case 'best-fit':
      chosen = viable.reduce((a, b) => a.length < b.length ? a : b);
      break;
    case 'worst-fit':
      chosen = viable.reduce((a, b) => a.length > b.length ? a : b);
      break;
  }

  return Array.from({ length: size }, (_, i) => chosen.start + i);
}

export function allocateBlocks(
  disk: DiskBlock[],
  size: number,
  fileId: string,
  allocationStrategy: AllocationStrategy = 'contiguous',
  freeSpaceStrategy: FreeSpaceStrategy = 'first-fit'
): { disk: DiskBlock[]; allocatedBlocks: number[]; indexBlock: number | null } | null {
  const newDisk = disk.map(b => ({ ...b }));
  const freeCount = newDisk.filter(b => b.state === 'free').length;

  const totalNeeded = allocationStrategy === 'indexed' ? size + 1 : size;
  if (freeCount < totalNeeded) return null;

  let selected: number[];
  let indexBlock: number | null = null;

  if (allocationStrategy === 'contiguous') {
    selected = findFreeBlocks(newDisk, size, freeSpaceStrategy);
    if (selected.length < size) return null;
  } else if (allocationStrategy === 'linked') {
    // Scattered allocation with linked list pointers
    const freeIndices = newDisk
      .map((b, i) => (b.state === 'free' ? i : -1))
      .filter(i => i !== -1);
    const shuffled = [...freeIndices].sort(() => Math.random() - 0.5);
    selected = shuffled.slice(0, size).sort((a, b) => a - b);
    if (selected.length < size) return null;
  } else {
    // Indexed: first free block becomes index block
    const freeIndices = newDisk
      .map((b, i) => (b.state === 'free' ? i : -1))
      .filter(i => i !== -1);
    if (freeIndices.length < size + 1) return null;
    indexBlock = freeIndices[0];
    const dataBlocks = freeIndices.slice(1);
    const shuffled = [...dataBlocks].sort(() => Math.random() - 0.5);
    selected = shuffled.slice(0, size).sort((a, b) => a - b);

    // Mark index block
    newDisk[indexBlock] = { ...newDisk[indexBlock], state: 'used', fileId, fragment: -1, nextBlock: null };
  }

  // Mark selected blocks
  selected.forEach((blockIdx, fragment) => {
    newDisk[blockIdx] = {
      ...newDisk[blockIdx],
      state: 'used',
      fileId,
      fragment,
      nextBlock: allocationStrategy === 'linked' ? (selected[fragment + 1] ?? null) : null,
    };
  });

  return { disk: newDisk, allocatedBlocks: selected, indexBlock };
}

export function deallocateFile(disk: DiskBlock[], fileId: string): DiskBlock[] {
  return disk.map(b =>
    b.fileId === fileId ? { ...b, state: 'free' as BlockState, fileId: null, fragment: 0, nextBlock: null } : { ...b }
  );
}

export function calculateFragmentation(blocks: number[]): number {
  if (blocks.length <= 1) return 0;
  let gaps = 0;
  for (let i = 1; i < blocks.length; i++) {
    if (blocks[i] !== blocks[i - 1] + 1) gaps++;
  }
  return gaps / (blocks.length - 1);
}

export function calculateDiskStats(disk: DiskBlock[]): DiskStats {
  const used = disk.filter(b => b.state === 'used').length;
  const free = disk.filter(b => b.state === 'free').length;
  const corrupted = disk.filter(b => b.state === 'corrupted').length;

  const fileBlocks = new Map<string, number[]>();
  disk.forEach(b => {
    if (b.fileId && b.fragment >= 0) {
      if (!fileBlocks.has(b.fileId)) fileBlocks.set(b.fileId, []);
      fileBlocks.get(b.fileId)!.push(b.id);
    }
  });

  let totalFrag = 0;
  let fileCount = 0;
  fileBlocks.forEach(blocks => {
    totalFrag += calculateFragmentation(blocks);
    fileCount++;
  });

  const fragmentation = fileCount > 0 ? totalFrag / fileCount : 0;
  const baseSpeed = 5;
  const readSpeed = baseSpeed * (1 + fragmentation * 3);
  const writeSpeed = baseSpeed * 1.5 * (1 + fragmentation * 2);

  return {
    totalBlocks: TOTAL_BLOCKS,
    usedBlocks: used,
    freeBlocks: free,
    corruptedBlocks: corrupted,
    fragmentation,
    readSpeed: Math.round(readSpeed * 10) / 10,
    writeSpeed: Math.round(writeSpeed * 10) / 10,
  };
}

export function simulateCrash(disk: DiskBlock[], severity: number, crashType: CrashType): {
  disk: DiskBlock[];
  corruptedFiles: string[];
  crashDetails: string;
} {
  const newDisk = disk.map(b => ({ ...b }));
  const usedBlocks = newDisk.filter(b => b.state === 'used');
  const corruptedFiles = new Set<string>();
  let details = '';

  switch (crashType) {
    case 'power-failure': {
      // Power failure: corrupts random blocks, may leave uncommitted writes
      const numCorrupt = Math.floor(usedBlocks.length * severity * 0.5);
      const shuffled = [...usedBlocks].sort(() => Math.random() - 0.5);
      shuffled.slice(0, numCorrupt).forEach(b => {
        const idx = newDisk.findIndex(bl => bl.id === b.id);
        if (b.fileId) corruptedFiles.add(b.fileId);
        newDisk[idx] = { ...newDisk[idx], state: 'corrupted' };
      });
      details = `Power failure: ${numCorrupt} blocks corrupted, ${corruptedFiles.size} files affected`;
      break;
    }
    case 'kernel-panic': {
      // Kernel panic: corrupts more aggressively, breaks linked chains
      const numCorrupt = Math.floor(usedBlocks.length * severity * 0.7);
      const shuffled = [...usedBlocks].sort(() => Math.random() - 0.5);
      shuffled.slice(0, numCorrupt).forEach(b => {
        const idx = newDisk.findIndex(bl => bl.id === b.id);
        if (b.fileId) corruptedFiles.add(b.fileId);
        newDisk[idx] = { ...newDisk[idx], state: 'corrupted', nextBlock: null };
      });
      details = `Kernel panic: ${numCorrupt} blocks corrupted, linked chains broken`;
      break;
    }
    case 'disk-error': {
      // Disk error: corrupts contiguous regions
      const regionStart = Math.floor(Math.random() * (TOTAL_BLOCKS - 20)) + 4;
      const regionSize = Math.floor(severity * 40) + 5;
      for (let i = regionStart; i < Math.min(regionStart + regionSize, TOTAL_BLOCKS); i++) {
        if (newDisk[i].state === 'used') {
          if (newDisk[i].fileId) corruptedFiles.add(newDisk[i].fileId);
          newDisk[i] = { ...newDisk[i], state: 'corrupted', nextBlock: null };
        }
      }
      details = `Disk error at blocks ${regionStart}-${regionStart + regionSize}: region corrupted`;
      break;
    }
  }

  return { disk: newDisk, corruptedFiles: Array.from(corruptedFiles), crashDetails: details };
}

export function recoverDisk(disk: DiskBlock[]): {
  disk: DiskBlock[];
  recoveredBlocks: number;
} {
  let recovered = 0;
  const newDisk = disk.map(b => {
    if (b.state === 'corrupted') {
      recovered++;
      return { ...b, state: 'free' as BlockState, fileId: null, fragment: 0, nextBlock: null };
    }
    return { ...b };
  });
  return { disk: newDisk, recoveredBlocks: recovered };
}

// fsck - File System Consistency Check
export function fsck(disk: DiskBlock[], files: Map<string, FileEntry>): FsckResult {
  const details: string[] = [];
  let orphanedBlocks = 0;
  let brokenChains = 0;
  let inconsistencies = 0;

  // Check 1: Orphaned blocks - blocks marked used but no file references them
  const referencedBlocks = new Set<number>();
  files.forEach(f => {
    f.blocks.forEach(b => referencedBlocks.add(b));
    if (f.indexBlock !== null) referencedBlocks.add(f.indexBlock);
  });

  disk.forEach(b => {
    if (b.state === 'used' && b.fileId && !referencedBlocks.has(b.id)) {
      orphanedBlocks++;
    }
  });
  if (orphanedBlocks > 0) details.push(`Found ${orphanedBlocks} orphaned blocks`);

  // Check 2: Broken linked chains
  files.forEach(f => {
    if (f.allocationStrategy === 'linked') {
      for (let i = 0; i < f.blocks.length - 1; i++) {
        const block = disk[f.blocks[i]];
        if (block && block.nextBlock !== f.blocks[i + 1]) {
          brokenChains++;
        }
      }
    }
  });
  if (brokenChains > 0) details.push(`Found ${brokenChains} broken linked chains`);

  // Check 3: File-block inconsistencies
  files.forEach(f => {
    f.blocks.forEach(blockId => {
      const block = disk[blockId];
      if (!block || block.state !== 'used' || block.fileId !== f.id) {
        inconsistencies++;
      }
    });
  });
  if (inconsistencies > 0) details.push(`Found ${inconsistencies} file-block inconsistencies`);

  if (details.length === 0) details.push('File system is consistent — no issues found');

  return { orphanedBlocks, brokenChains, inconsistencies, repaired: false, details };
}

export function fsckRepair(disk: DiskBlock[], files: Map<string, FileEntry>): {
  disk: DiskBlock[];
  files: Map<string, FileEntry>;
  result: FsckResult;
} {
  const newDisk = disk.map(b => ({ ...b }));
  const newFiles = new Map(files);
  const details: string[] = [];
  let orphanedBlocks = 0;
  let brokenChains = 0;
  let inconsistencies = 0;

  // Fix orphaned blocks
  const referencedBlocks = new Set<number>();
  newFiles.forEach(f => {
    f.blocks.forEach(b => referencedBlocks.add(b));
    if (f.indexBlock !== null) referencedBlocks.add(f.indexBlock);
  });

  newDisk.forEach((b, i) => {
    if (b.state === 'used' && b.fileId && !referencedBlocks.has(b.id)) {
      newDisk[i] = { ...b, state: 'free', fileId: null, fragment: 0, nextBlock: null };
      orphanedBlocks++;
    }
  });
  if (orphanedBlocks > 0) details.push(`Freed ${orphanedBlocks} orphaned blocks`);

  // Fix broken chains
  newFiles.forEach((f, fId) => {
    if (f.allocationStrategy === 'linked') {
      let fixed = false;
      const validBlocks = f.blocks.filter(blockId => {
        const block = newDisk[blockId];
        return block && block.state === 'used' && block.fileId === f.id;
      });
      if (validBlocks.length !== f.blocks.length) {
        brokenChains++;
        fixed = true;
      }
      // Re-link valid blocks
      validBlocks.forEach((blockId, i) => {
        newDisk[blockId] = { ...newDisk[blockId], nextBlock: validBlocks[i + 1] ?? null, fragment: i };
      });
      if (fixed) {
        newFiles.set(fId, { ...f, blocks: validBlocks, size: validBlocks.length });
      }
    }
  });
  if (brokenChains > 0) details.push(`Repaired ${brokenChains} broken chains`);

  // Fix inconsistencies - remove files with missing blocks
  const toRemove: string[] = [];
  newFiles.forEach((f, fId) => {
    const badBlocks = f.blocks.filter(blockId => {
      const block = newDisk[blockId];
      return !block || block.state !== 'used' || block.fileId !== f.id;
    });
    if (badBlocks.length > 0) {
      inconsistencies++;
      toRemove.push(fId);
    }
  });
  toRemove.forEach(fId => {
    const f = newFiles.get(fId);
    if (f) {
      f.blocks.forEach(blockId => {
        if (newDisk[blockId]?.fileId === fId) {
          newDisk[blockId] = { ...newDisk[blockId], state: 'free', fileId: null, fragment: 0, nextBlock: null };
        }
      });
      newFiles.delete(fId);
    }
  });
  if (inconsistencies > 0) details.push(`Removed ${inconsistencies} inconsistent files`);

  if (details.length === 0) details.push('No repairs needed — file system is consistent');

  return {
    disk: newDisk,
    files: newFiles,
    result: { orphanedBlocks, brokenChains, inconsistencies, repaired: true, details },
  };
}

export function defragmentDisk(
  disk: DiskBlock[],
  files: Map<string, FileEntry>
): { disk: DiskBlock[]; files: Map<string, FileEntry> } {
  const newDisk = createInitialDisk();
  const newFiles = new Map(files);

  const fileList = Array.from(newFiles.values()).filter(f => !f.isDirectory);
  let nextFreeBlock = 4;

  fileList.forEach(file => {
    const newBlocks: number[] = [];
    for (let i = 0; i < file.size; i++) {
      if (nextFreeBlock < TOTAL_BLOCKS) {
        newDisk[nextFreeBlock] = {
          id: nextFreeBlock,
          state: 'used',
          fileId: file.id,
          fragment: i,
          nextBlock: file.allocationStrategy === 'linked' ? nextFreeBlock + 1 : null,
        };
        newBlocks.push(nextFreeBlock);
        nextFreeBlock++;
      }
    }
    // Fix last linked block
    if (file.allocationStrategy === 'linked' && newBlocks.length > 0) {
      newDisk[newBlocks[newBlocks.length - 1]].nextBlock = null;
    }
    newFiles.set(file.id, { ...file, blocks: newBlocks, fragmentation: 0 });
  });

  return { disk: newDisk, files: newFiles };
}

export function createJournalEntry(
  operation: JournalEntry['operation'],
  fileId: string,
  fileName: string,
  details: string,
  committed: boolean = true
): JournalEntry {
  return {
    id: ++journalCounter,
    timestamp: Date.now(),
    operation,
    fileId,
    fileName,
    details,
    committed,
  };
}
