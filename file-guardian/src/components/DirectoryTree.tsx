import { FileEntry, DirectoryEntry } from '@/lib/fileSystem';
import { Folder, File, Trash2 } from 'lucide-react';

interface DirectoryTreeProps {
  directories: Map<string, DirectoryEntry>;
  files: Map<string, FileEntry>;
  onSelectFile?: (fileId: string) => void;
  onDeleteFile?: (fileId: string) => void;
  selectedFile?: string | null;
}

const strategyBadge: Record<string, string> = {
  contiguous: 'text-primary',
  linked: 'text-info',
  indexed: 'text-warning',
};

function TreeNode({
  nodeId, directories, files, depth, onSelectFile, onDeleteFile, selectedFile,
}: {
  nodeId: string;
  directories: Map<string, DirectoryEntry>;
  files: Map<string, FileEntry>;
  depth: number;
  onSelectFile?: (fileId: string) => void;
  onDeleteFile?: (fileId: string) => void;
  selectedFile?: string | null;
}) {
  const dir = directories.get(nodeId);
  const file = files.get(nodeId);

  if (dir) {
    return (
      <div>
        <div className="flex items-center gap-2 py-1 px-2 rounded text-sm text-accent hover:bg-secondary/50 transition-colors"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}>
          <Folder className="w-4 h-4 shrink-0" />
          <span className="font-medium">{dir.name}</span>
        </div>
        {dir.children.map(childId => (
          <TreeNode key={childId} nodeId={childId} directories={directories}
            files={files} depth={depth + 1}
            onSelectFile={onSelectFile} onDeleteFile={onDeleteFile} selectedFile={selectedFile} />
        ))}
      </div>
    );
  }

  if (file) {
    return (
      <div
        className={`flex items-center gap-1.5 py-1 px-2 rounded text-xs cursor-pointer transition-colors group ${
          selectedFile === nodeId ? 'bg-primary/20 text-primary' : 'text-foreground hover:bg-secondary/50'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelectFile?.(nodeId)}
      >
        <File className="w-3.5 h-3.5 shrink-0" />
        <span className="flex-1 truncate">{file.name}</span>
        <span className={`text-[9px] font-mono ${strategyBadge[file.allocationStrategy] || 'text-muted-foreground'}`}>
          {file.allocationStrategy.charAt(0).toUpperCase()}
        </span>
        <span className="text-[10px] text-muted-foreground">{file.size}B</span>
        <button onClick={(e) => { e.stopPropagation(); onDeleteFile?.(nodeId); }}
          className="opacity-0 group-hover:opacity-100 text-danger hover:text-danger/80 transition-opacity">
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return null;
}

export default function DirectoryTree({ directories, files, onSelectFile, onDeleteFile, selectedFile }: DirectoryTreeProps) {
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground mb-2">
        Directory Tree
      </h3>
      <div className="rounded-lg border border-border bg-background p-2 max-h-52 overflow-y-auto">
        <TreeNode nodeId="root" directories={directories} files={files} depth={0}
          onSelectFile={onSelectFile} onDeleteFile={onDeleteFile} selectedFile={selectedFile} />
        {directories.get('root')?.children.length === 0 && (
          <p className="text-[10px] text-muted-foreground text-center py-4">Empty file system</p>
        )}
      </div>
    </div>
  );
}
