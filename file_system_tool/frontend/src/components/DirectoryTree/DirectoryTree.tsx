import React, { useEffect, useState } from 'react';
import { ChevronRight, ChevronDown, Folder, File, FolderOpen } from 'lucide-react';
import { apiClient } from '@/api/client';
import { useFileSystemStore } from '@/store/store';
import type { FileInfo } from '@/types';

export const DirectoryTree: React.FC = () => {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['/']));
  const { currentPath, setCurrentPath, setDirectoryListing, setSelectedFile } = useFileSystemStore();

  useEffect(() => {
    loadDirectory(currentPath);
  }, [currentPath]);

  const loadDirectory = async (path: string) => {
    try {
      const response = await apiClient.listDirectory(path);
      setDirectoryListing(response.data.items);
    } catch (error) {
      console.error('Failed to load directory:', error);
    }
  };

  const toggleExpand = (path: string) => {
    const newExpanded = new Set(expandedPaths);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedPaths(newExpanded);
  };

  return (
    <div className="space-y-1">
      <TreeNode
        item={{
          name: 'root',
          path: '/',
          type: 'directory',
          created: new Date().toISOString(),
          modified: new Date().toISOString(),
        }}
        level={0}
        expandedPaths={expandedPaths}
        toggleExpand={toggleExpand}
        onSelect={setSelectedFile}
      />
    </div>
  );
};

interface TreeNodeProps {
  item: FileInfo;
  level: number;
  expandedPaths: Set<string>;
  toggleExpand: (path: string) => void;
  onSelect: (item: FileInfo) => void;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  item,
  level,
  expandedPaths,
  toggleExpand,
  onSelect,
}) => {
  const [children, setChildren] = useState<FileInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const isExpanded = expandedPaths.has(item.path);

  useEffect(() => {
    if (isExpanded && item.type === 'directory') {
      loadChildren();
    }
  }, [isExpanded, item.path]);

  const loadChildren = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.listDirectory(item.path);
      setChildren(response.data.items);
    } catch (error) {
      console.error('Failed to load children:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClick = () => {
    if (item.type === 'directory') {
      toggleExpand(item.path);
    }
    onSelect(item);
  };

  return (
    <div>
      <div
        className={`
          flex items-center space-x-2 px-2 py-1.5 rounded cursor-pointer
          hover:bg-gray-100 transition-colors
          ${level > 0 ? `ml-${level * 4}` : ''}
        `}
        onClick={handleClick}
        style={{ paddingLeft: `${level * 16}px` }}
      >
        {item.type === 'directory' ? (
          <>
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-500" />
            )}
            {isExpanded ? (
              <FolderOpen className="w-4 h-4 text-blue-500" />
            ) : (
              <Folder className="w-4 h-4 text-blue-500" />
            )}
          </>
        ) : (
          <>
            <div className="w-4" /> {/* Spacer */}
            <File className="w-4 h-4 text-gray-500" />
          </>
        )}

        <span className="text-sm font-medium text-gray-700">
          {item.name}
        </span>

        {item.size && (
          <span className="text-xs text-gray-500 ml-auto">
            {formatFileSize(item.size)}
          </span>
        )}
      </div>

      {isExpanded && item.type === 'directory' && (
        <div>
          {isLoading ? (
            <div className="text-xs text-gray-500 ml-8">Loading...</div>
          ) : (
            children.map((child) => (
              <TreeNode
                key={child.path}
                item={child}
                level={level + 1}
                expandedPaths={expandedPaths}
                toggleExpand={toggleExpand}
                onSelect={onSelect}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
