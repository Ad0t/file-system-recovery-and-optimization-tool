import React, { useEffect, useState } from 'react';
import { useFileSystemStore } from '@/store/store';
import { apiClient } from '@/api/client';
import type { BlockState } from '@/types';

export const DiskVisualizer: React.FC = () => {
  const { diskVisualization, setDiskVisualization } = useFileSystemStore();
  const [hoveredBlock, setHoveredBlock] = useState<number | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<BlockState | null>(null);

  useEffect(() => {
    loadVisualization();

    // Refresh every 5 seconds
    const interval = setInterval(loadVisualization, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadVisualization = async () => {
    try {
      const response = await apiClient.getDiskVisualization();
      setDiskVisualization(response.data);
    } catch (error) {
      console.error('Failed to load visualization:', error);
    }
  };

  if (!diskVisualization) {
    return <div className="text-center py-8 text-gray-500">Loading...</div>;
  }

  const blocksPerRow = diskVisualization.blocks_per_row;
  const rows = Math.ceil(diskVisualization.total_blocks / blocksPerRow);

  return (
    <div className="space-y-4">
      {/* Statistics */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="bg-gray-50 p-3 rounded">
          <div className="text-gray-500">Total Blocks</div>
          <div className="text-lg font-semibold">
            {diskVisualization.statistics.total_blocks}
          </div>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <div className="text-gray-500">Used</div>
          <div className="text-lg font-semibold">
            {diskVisualization.statistics.used_blocks} ({diskVisualization.statistics.usage_percentage.toFixed(1)}%)
          </div>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <div className="text-gray-500">Free</div>
          <div className="text-lg font-semibold">
            {diskVisualization.statistics.free_blocks}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center space-x-4 text-sm">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-green-200 border border-green-400 rounded" />
          <span>Free</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 bg-red-200 border border-red-400 rounded" />
          <span>Allocated</span>
        </div>
      </div>

      {/* Block Grid */}
      <div className="border border-gray-200 rounded-lg p-4 overflow-auto max-h-96">
        <div
          className="grid gap-0.5"
          style={{
            gridTemplateColumns: `repeat(${blocksPerRow}, minmax(0, 1fr))`,
          }}
        >
          {diskVisualization.block_states.map((block) => (
            <BlockCell
              key={block.block_number}
              block={block}
              isHovered={hoveredBlock === block.block_number}
              onHover={setHoveredBlock}
              onClick={() => setSelectedBlock(block)}
            />
          ))}
        </div>
      </div>

      {/* Hover Tooltip */}
      {hoveredBlock !== null && (
        <BlockTooltip
          block={diskVisualization.block_states[hoveredBlock]}
        />
      )}

      {/* Selected Block Details */}
      {selectedBlock && (
        <BlockDetails
          block={selectedBlock}
          onClose={() => setSelectedBlock(null)}
        />
      )}
    </div>
  );
};

interface BlockCellProps {
  block: BlockState;
  isHovered: boolean;
  onHover: (blockNum: number | null) => void;
  onClick: () => void;
}

const BlockCell: React.FC<BlockCellProps> = ({ block, isHovered, onHover, onClick }) => {
  return (
    <div
      className={`
        aspect-square rounded-sm cursor-pointer transition-all
        ${isHovered ? 'ring-2 ring-blue-500 scale-110' : ''}
      `}
      style={{
        backgroundColor: block.color,
        borderWidth: '1px',
        borderColor: block.status === 'allocated' ? '#f87171' : '#86efac',
      }}
      onMouseEnter={() => onHover(block.block_number)}
      onMouseLeave={() => onHover(null)}
      onClick={onClick}
    />
  );
};

interface BlockTooltipProps {
  block: BlockState;
}

const BlockTooltip: React.FC<BlockTooltipProps> = ({ block }) => {
  return (
    <div className="bg-gray-900 text-white text-xs rounded p-2 absolute">
      <div>Block #{block.block_number}</div>
      <div>Status: {block.status}</div>
      {block.owner_inode && <div>Owner: Inode #{block.owner_inode}</div>}
    </div>
  );
};

interface BlockDetailsProps {
  block: BlockState;
  onClose: () => void;
}

const BlockDetails: React.FC<BlockDetailsProps> = ({ block, onClose }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Block Details</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Block Number:</span>
            <span className="font-medium">{block.block_number}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Status:</span>
            <span className="font-medium capitalize">{block.status}</span>
          </div>
          {block.owner_inode && (
            <>
              <div className="flex justify-between">
                <span className="text-gray-600">Owner Inode:</span>
                <span className="font-medium">#{block.owner_inode}</span>
              </div>
              {block.owner_file && (
                <div className="flex justify-between">
                  <span className="text-gray-600">File:</span>
                  <span className="font-medium">{block.owner_file}</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
