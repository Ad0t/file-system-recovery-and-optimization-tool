import axios from 'axios';
import type { AxiosInstance } from 'axios';

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = '/api') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // File Operations
  async createFile(path: string, size: number) {
    return this.client.post('/files/create', { path, size });
  }

  async createDirectory(path: string) {
    return this.client.post('/files/directory', { path });
  }

  async deleteItem(path: string, recursive: boolean = false) {
    return this.client.delete('/files/delete', { data: { path, recursive } });
  }

  async listDirectory(path: string = '/') {
    return this.client.get('/files/list', { params: { path } });
  }

  async getDiskInfo() {
    return this.client.get('/files/disk/info');
  }

  async getDiskVisualization() {
    return this.client.get('/files/disk/visualization');
  }

  // Recovery Operations
  async injectCrash(crash_type: string, severity: string = 'medium') {
    return this.client.post('/recovery/crash/inject', { crash_type, severity });
  }

  async recoverSystem() {
    return this.client.post('/recovery/recover');
  }

  async runFsck(auto_repair: boolean = false) {
    return this.client.post('/recovery/fsck', null, { params: { auto_repair } });
  }

  // Optimization Operations
  async defragment(inode_number?: number, strategy: string = 'most_fragmented_first') {
    return this.client.post('/optimization/defragment', { inode_number, strategy });
  }

  async getFragmentationAnalysis() {
    return this.client.get('/optimization/fragmentation');
  }

  async configurCache(cache_size: number, strategy: string) {
    return this.client.post('/optimization/cache/config', { cache_size, strategy });
  }

  async getCacheStats() {
    return this.client.get('/optimization/cache/stats');
  }

  // Performance Metrics
  async getCurrentMetrics() {
    return this.client.get('/metrics/current');
  }

  async runBenchmark(test_types: string[] = ['read', 'write']) {
    return this.client.post('/metrics/benchmark', { test_types });
  }
}

export const apiClient = new ApiClient();
