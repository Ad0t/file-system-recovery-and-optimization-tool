import React, { useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Activity, Cpu, HardDrive, Zap } from 'lucide-react';
import { useFileSystemStore } from '@/store/store';

export const PerformanceDashboard: React.FC = () => {
  const { currentMetrics, metricsHistory } = useFileSystemStore();

  if (!currentMetrics) {
    return <div className="text-center py-8 text-gray-500">Loading metrics...</div>;
  }

  // Helper to safely format numbers
  const formatNum = (val: number | undefined, decimals = 1) =>
    val !== undefined && !isNaN(val) ? val.toFixed(decimals) : '0.0';

  return (
    <div className="space-y-4">
      {/* Current Metrics Cards */}
      <div className="grid grid-cols-1 gap-3">
        <MetricCard
          icon={<HardDrive className="w-5 h-5" />}
          label="Disk Usage"
          value={`${formatNum(currentMetrics.disk_usage_percentage)}%`}
          color={getColorForPercentage(currentMetrics.disk_usage_percentage ?? 0)}
        />

        <MetricCard
          icon={<Activity className="w-5 h-5" />}
          label="Fragmentation"
          value={`${formatNum(currentMetrics.fragmentation_percentage)}%`}
          color={getColorForFragmentation(currentMetrics.fragmentation_percentage ?? 0)}
        />

        <MetricCard
          icon={<Zap className="w-5 h-5" />}
          label="Cache Hit Rate"
          value={`${formatNum(currentMetrics.cache_hit_rate)}%`}
          color={getColorForHitRate(currentMetrics.cache_hit_rate ?? 0)}
        />

        <MetricCard
          icon={<Cpu className="w-5 h-5" />}
          label="Read Throughput"
          value={`${formatNum(currentMetrics.read_throughput_mbps)} MB/s`}
          color="text-blue-600"
        />

        <MetricCard
          icon={<Cpu className="w-5 h-5" />}
          label="Write Throughput"
          value={`${formatNum(currentMetrics.write_throughput_mbps)} MB/s`}
          color="text-purple-600"
        />

        <MetricCard
          icon={<Activity className="w-5 h-5" />}
          label="IOPS"
          value={(currentMetrics.iops ?? 0).toString()}
          color="text-indigo-600"
        />
      </div>

      {/* Charts */}
      {metricsHistory.length > 1 && (
        <div className="space-y-4 mt-6">
          <h3 className="text-sm font-semibold text-gray-700">Performance History</h3>

          {/* Throughput Chart */}
          <div className="bg-gray-50 p-3 rounded-lg">
            <h4 className="text-xs font-medium text-gray-600 mb-2">Throughput</h4>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={metricsHistory.slice(-20)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="timestamp" hide />
                <YAxis fontSize={10} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="read_throughput_mbps"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Read"
                />
                <Line
                  type="monotone"
                  dataKey="write_throughput_mbps"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                  name="Write"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Cache Hit Rate Chart */}
          <div className="bg-gray-50 p-3 rounded-lg">
            <h4 className="text-xs font-medium text-gray-600 mb-2">Cache Hit Rate</h4>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={metricsHistory.slice(-20)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="timestamp" hide />
                <YAxis fontSize={10} domain={[0, 100]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="cache_hit_rate"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  name="Hit Rate %"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
};

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ icon, label, value, color }) => {
  return (
    <div className="bg-gray-50 p-3 rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={color}>{icon}</div>
          <span className="text-xs text-gray-600">{label}</span>
        </div>
        <span className={`text-lg font-bold ${color}`}>{value}</span>
      </div>
    </div>
  );
};

function getColorForPercentage(percentage: number): string {
  if (percentage < 50) return 'text-green-600';
  if (percentage < 80) return 'text-yellow-600';
  return 'text-red-600';
}

function getColorForFragmentation(percentage: number): string {
  if (percentage < 30) return 'text-green-600';
  if (percentage < 50) return 'text-yellow-600';
  return 'text-red-600';
}

function getColorForHitRate(percentage: number): string {
  if (percentage > 70) return 'text-green-600';
  if (percentage > 50) return 'text-yellow-600';
  return 'text-red-600';
}
