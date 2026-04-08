// LRU Cache Manager for file system simulation

export interface CacheEntry {
  fileId: string;
  fileName: string;
  accessCount: number;
  lastAccess: number;
  size: number;
}

export interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  entries: CacheEntry[];
  maxSize: number;
  currentSize: number;
}

export class CacheManager {
  private cache: Map<string, CacheEntry> = new Map();
  private maxSize: number;
  private hits = 0;
  private misses = 0;

  constructor(maxSize: number = 16) {
    this.maxSize = maxSize;
  }

  access(fileId: string, fileName: string, size: number): boolean {
    if (this.cache.has(fileId)) {
      const entry = this.cache.get(fileId)!;
      this.cache.delete(fileId);
      this.cache.set(fileId, { ...entry, accessCount: entry.accessCount + 1, lastAccess: Date.now() });
      this.hits++;
      return true; // cache hit
    }

    this.misses++;

    // Evict LRU if full
    let currentSize = this.getCurrentSize();
    while (currentSize + size > this.maxSize && this.cache.size > 0) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) {
        const evicted = this.cache.get(oldestKey);
        currentSize -= evicted?.size ?? 0;
        this.cache.delete(oldestKey);
      }
    }

    this.cache.set(fileId, { fileId, fileName, accessCount: 1, lastAccess: Date.now(), size });
    return false; // cache miss
  }

  remove(fileId: string) {
    this.cache.delete(fileId);
  }

  clear() {
    this.cache.clear();
    this.hits = 0;
    this.misses = 0;
  }

  private getCurrentSize(): number {
    let size = 0;
    this.cache.forEach(e => size += e.size);
    return size;
  }

  getStats(): CacheStats {
    const total = this.hits + this.misses;
    return {
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? this.hits / total : 0,
      entries: Array.from(this.cache.values()).reverse(),
      maxSize: this.maxSize,
      currentSize: this.getCurrentSize(),
    };
  }

  setMaxSize(size: number) {
    this.maxSize = size;
    // Evict if needed
    let currentSize = this.getCurrentSize();
    while (currentSize > this.maxSize && this.cache.size > 0) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) {
        const evicted = this.cache.get(oldestKey);
        currentSize -= evicted?.size ?? 0;
        this.cache.delete(oldestKey);
      }
    }
  }
}
