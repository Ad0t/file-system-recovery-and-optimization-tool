export type FileType = 'file' | 'directory';

export interface FileInfo {
  name: string;
  path: string;
  type: FileType;
  size?: number;
  created: string;
  modified: string;
  inode_number?: number;
  blocks?: number[];
}

export interface DirectoryListing {
  path: string;
  items: FileInfo[];
}

export interface DiskInfo {
  total_blocks: number;
  block_size: number;
  total_capacity_mb: number;
  used_blocks: number;
  free_blocks: number;
  usage_percentage: number;
}

export interface BlockState {
  block_number: number;
  status: 'free' | 'allocated';
  color: string;
  owner_inode?: number;
  owner_file?: string;
}

export interface DiskVisualization {
  total_blocks: number;
  blocks_per_row: number;
  block_states: BlockState[];
  statistics: DiskInfo;
}

export interface CrashReport {
  crash_id: number;
  crash_type: string;
  timestamp: string;
  affected_blocks: number[];
  severity: string;
  recoverable: boolean;
  description: string;
}

export interface RecoveryReport {
  success: boolean;
  recovered_transactions: number;
  rolled_back_transactions: number;
  recovery_time: number;
  errors: string[];
}

export interface DefragmentationReport {
  success: boolean;
  files_defragmented: number;
  fragmentation_before: number;
  fragmentation_after: number;
  blocks_moved: number;
  time_taken: number;
}

export interface PerformanceMetrics {
  timestamp: string;
  disk_usage_percentage: number;
  fragmentation_percentage: number;
  cache_hit_rate: number;
  read_throughput_mbps: number;
  write_throughput_mbps: number;
  iops: number;
  free_space_mb: number;
}

export interface LogEntry {
  timestamp: string;
  level: 'debug' | 'info' | 'warning' | 'error' | 'success';
  message: string;
}

export interface WebSocketMessage {
  type: string;
  data?: any;
  message?: string;
}
