import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Event } from "../lib/api";

interface AnomalyChartProps {
  events: Event[];
  threshold?: number;
  height?: number;
}

const AnomalyChart: React.FC<AnomalyChartProps> = ({
  events,
  threshold = 0.7,
  height = 300,
}) => {
  // Prepare data for the chart
  const chartData = events
    .sort((a, b) => a.timestamp_seconds - b.timestamp_seconds)
    .map((event, index) => ({
      key: event.id || `${event.frame_number}-${event.timestamp_seconds}`, // Add unique key
      index,
      timestamp: event.timestamp_seconds,
      anomaly_score: event.anomaly_score,
      confidence: event.confidence,
      event_type: event.event_type,
      is_alert: event.is_alert,
      frame_number: event.frame_number,
    }));

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-medium text-gray-900">Frame {data.frame_number}</p>
          <p className="text-sm text-gray-600">
            Time: {formatTime(data.timestamp)}
          </p>
          <p className="text-sm">
            <span className="text-gray-600">Anomaly Score:</span>{" "}
            <span
              className={`font-medium ${
                data.anomaly_score > threshold
                  ? "text-red-600"
                  : "text-green-600"
              }`}
            >
              {data.anomaly_score.toFixed(3)}
            </span>
          </p>
          <p className="text-sm">
            <span className="text-gray-600">Confidence:</span>{" "}
            <span className="font-medium text-blue-600">
              {(data.confidence * 100).toFixed(1)}%
            </span>
          </p>
          <p className="text-sm">
            <span className="text-gray-600">Type:</span>{" "}
            <span className="font-medium text-purple-600">
              {data.event_type.replace("_", " ")}
            </span>
          </p>
          {data.is_alert && (
            <p className="text-sm font-medium text-red-600">
              🚨 Alert Triggered
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  const getPointColor = (score: number, isAlert: boolean) => {
    if (isAlert) return "#dc2626"; // red-600
    if (score > threshold) return "#f59e0b"; // amber-500
    return "#22c55e"; // green-500
  };

  return (
    <div className="w-full">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">
          Anomaly Detection Timeline
        </h3>
        <div className="flex items-center space-x-4 text-sm">
          <div className="flex items-center">
            <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
            <span className="text-gray-600">Normal (&lt; {threshold})</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-amber-500 rounded-full mr-2"></div>
            <span className="text-gray-600">Anomaly (&gt; {threshold})</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-red-600 rounded-full mr-2"></div>
            <span className="text-gray-600">Alert</span>
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded-lg border border-gray-200">
        {" "}
        <ResponsiveContainer width="100%" height={height}>
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTime}
              stroke="#6b7280"
              fontSize={12}
            />
            <YAxis
              domain={[0, 1]}
              stroke="#6b7280"
              fontSize={12}
              tickFormatter={(value) => value.toFixed(1)}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Threshold line */}
            <ReferenceLine
              y={threshold}
              stroke="#ef4444"
              strokeDasharray="5 5"
              label={{ value: `Threshold (${threshold})`, position: "top" }}
            />

            {/* Anomaly score line */}
            <Line
              type="monotone"
              dataKey="anomaly_score"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={(props: any) => {
                const { cx, cy, payload } = props;
                return (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={payload.is_alert ? 6 : 4}
                    fill={getPointColor(
                      payload.anomaly_score,
                      payload.is_alert
                    )}
                    stroke="#ffffff"
                    strokeWidth={2}
                  />
                );
              }}
              activeDot={{ r: 8, stroke: "#3b82f6", strokeWidth: 2 }}
            />

            {/* Confidence line */}
            <Line
              type="monotone"
              dataKey="confidence"
              stroke="#8b5cf6"
              strokeWidth={1}
              strokeDasharray="3 3"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Summary statistics */}
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-3 rounded-lg border border-gray-200 text-center">
          <p className="text-2xl font-bold text-gray-900">{events.length}</p>
          <p className="text-sm text-gray-600">Total Events</p>
        </div>
        <div className="bg-white p-3 rounded-lg border border-gray-200 text-center">
          <p className="text-2xl font-bold text-red-600">
            {events.filter((e) => e.anomaly_score > threshold).length}
          </p>
          <p className="text-sm text-gray-600">Anomalies</p>
        </div>
        <div className="bg-white p-3 rounded-lg border border-gray-200 text-center">
          <p className="text-2xl font-bold text-orange-600">
            {events.filter((e) => e.is_alert).length}
          </p>
          <p className="text-sm text-gray-600">Alerts</p>
        </div>
        <div className="bg-white p-3 rounded-lg border border-gray-200 text-center">
          <p className="text-2xl font-bold text-blue-600">
            {events.length > 0
              ? (
                  events.reduce((sum, e) => sum + e.anomaly_score, 0) /
                  events.length
                ).toFixed(3)
              : "0.000"}
          </p>
          <p className="text-sm text-gray-600">Avg Score</p>
        </div>
      </div>
    </div>
  );
};

export default AnomalyChart;
