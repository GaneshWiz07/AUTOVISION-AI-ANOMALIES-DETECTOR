import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { videoAPI, eventAPI, systemAPI, Video, Event } from "../lib/api.ts";
import AnomalyChart from "../components/AnomalyChart";
import LoadingSpinner from "../components/LoadingSpinner";
import {
  VideoCameraIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  ClockIcon,
  PlayIcon,
} from "@heroicons/react/24/outline";

const Dashboard = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [recentEvents, setRecentEvents] = useState<Event[]>([]);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadDashboardData();

    // Set up polling for videos that are processing (like Analytics does)
    const pollInterval = setInterval(async () => {
      try {
        const videosData = await videoAPI.getVideos();
        const processingVideos =
          videosData.videos?.filter(
            (v: Video) => v.upload_status === "processing"
          ) || [];

        if (processingVideos.length > 0) {
          // Refresh data if there are processing videos
          loadDashboardData();
        }
      } catch (error) {
        // Ignore polling errors
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError("");

      // Use same pattern as Analytics - no limit on initial load to get all data
      const [videosData, eventsData, statusResponse] = await Promise.all([
        videoAPI.getVideos(), // Remove limit to get all videos like Analytics
        eventAPI.getEvents(), // Get all events like Analytics
        systemAPI.getStatus(),
      ]);

      // Use same fallback pattern as Analytics
      setVideos(videosData.videos || []);
      setRecentEvents(eventsData.events || []);
      setSystemStatus(statusResponse);

      console.log("Dashboard data loaded:", {
        videos: videosData.videos?.length || 0,
        events: eventsData.events?.length || 0,
        status: statusResponse?.status || "unknown",
      });
    } catch (err) {
      console.error("Error loading dashboard data:", err);

      // Better error handling for different error types
      let errorMessage = "Failed to load dashboard data";
      if (err.response) {
        // The request was made and the server responded with a status code
        errorMessage = `Server error: ${err.response.status} - ${
          err.response.data?.detail || err.response.statusText
        }`;
        console.error("Response data:", err.response.data);
        console.error("Response status:", err.response.status);
      } else if (err.request) {
        // The request was made but no response was received
        errorMessage =
          "No response from server. Check if the backend is running.";
        console.error("Request made but no response:", err.request);
      } else {
        // Something happened in setting up the request
        errorMessage = err.message || "Unknown error occurred";
        console.error("Error setting up request:", err.message);
      }

      setError(errorMessage);
      // Set empty arrays as fallback
      setVideos([]);
      setRecentEvents([]);
      setSystemStatus({ status: "error" });
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case "completed":
        return "text-green-600 bg-green-100";
      case "processing":
        return "text-blue-600 bg-blue-100";
      case "failed":
        return "text-red-600 bg-red-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatFileSize = (bytes) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="md" />
      </div>
    );
  }
  // Calculate stats using the same logic as Analytics
  const alertEvents = recentEvents.filter((event) => event.is_alert);
  const processingVideos = videos.filter(
    (v) => v.upload_status === "processing"
  );

  return (
    <div className="space-y-8">
      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                Error loading dashboard data
              </h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error}</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={loadDashboardData}
                  className="bg-red-100 px-2 py-1 rounded text-sm text-red-800 hover:bg-red-200"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        </div>
      )}{" "}
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-600">
            Monitor your surveillance system and recent anomaly detections
          </p>
        </div>
        <button
          onClick={loadDashboardData}
          disabled={loading}
          className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50"
        >
          {loading ? (
            <LoadingSpinner size="sm" />
          ) : (
            <>
              <ChartBarIcon className="-ml-0.5 mr-2 h-4 w-4" />
              Refresh
            </>
          )}
        </button>
      </div>
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <VideoCameraIcon className="h-6 w-6 text-gray-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Total Videos
                  </dt>
                  <dd className="text-lg font-medium text-gray-900">
                    {videos.length}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <ExclamationTriangleIcon className="h-6 w-6 text-red-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Active Alerts
                  </dt>
                  <dd className="text-lg font-medium text-red-600">
                    {alertEvents.length}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <ChartBarIcon className="h-6 w-6 text-blue-400" />
              </div>
              <div className="ml-5 w-0 flex-1">
                {" "}
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    Total Events
                  </dt>
                  <dd className="text-lg font-medium text-blue-600">
                    {recentEvents.length}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>{" "}
        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <ClockIcon
                  className={`h-6 w-6 ${
                    processingVideos.length > 0
                      ? "text-yellow-400"
                      : systemStatus?.status === "healthy" || videos.length > 0
                      ? "text-green-400"
                      : "text-gray-400"
                  }`}
                />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">
                    System Status
                  </dt>
                  <dd
                    className={`text-lg font-medium ${
                      processingVideos.length > 0
                        ? "text-yellow-600"
                        : systemStatus?.status === "healthy" ||
                          videos.length > 0
                        ? "text-green-600"
                        : error
                        ? "text-red-600"
                        : "text-gray-600"
                    }`}
                  >
                    {processingVideos.length > 0
                      ? `Processing (${processingVideos.length})`
                      : systemStatus?.status === "healthy" || videos.length > 0
                      ? "Online"
                      : error
                      ? "Error"
                      : "Unknown"}
                  </dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* Recent Videos */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Recent Videos
            </h3>
            <Link
              to="/videos"
              className="text-sm font-medium text-primary-600 hover:text-primary-500"
            >
              View all
            </Link>
          </div>

          {videos.length === 0 ? (
            <div className="text-center py-8">
              <VideoCameraIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                No videos
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Get started by uploading your first surveillance video.
              </p>
              <div className="mt-6">
                <Link
                  to="/videos"
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
                >
                  <VideoCameraIcon className="-ml-1 mr-2 h-5 w-5" />
                  Upload Video
                </Link>
              </div>
            </div>
          ) : (
            <div className="overflow-hidden">
              <ul className="divide-y divide-gray-200">
                {videos.slice(0, 5).map((video) => (
                  <li key={video.id} className="py-4">
                    <div className="flex items-center space-x-4">
                      <div className="flex-shrink-0">
                        <div className="h-10 w-10 rounded-lg bg-gray-100 flex items-center justify-center">
                          <PlayIcon className="h-5 w-5 text-gray-600" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {video.original_name}
                        </p>
                        <div className="flex items-center space-x-2 text-sm text-gray-500">
                          <span>{formatFileSize(video.file_size)}</span>
                          {video.duration_seconds && (
                            <>
                              <span>•</span>
                              <span>
                                {formatDuration(video.duration_seconds)}
                              </span>
                            </>
                          )}
                          {video.resolution && (
                            <>
                              <span>•</span>
                              <span>{video.resolution}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="flex-shrink-0">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                            video.upload_status
                          )}`}
                        >
                          {video.upload_status}
                        </span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
      {/* Anomaly Chart */}
      {recentEvents.length > 0 && (
        <div className="bg-white shadow rounded-lg p-6">
          <AnomalyChart events={recentEvents} height={250} />
        </div>
      )}
      {/* Recent Events */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Recent Anomaly Events
            </h3>
            <Link
              to="/analytics"
              className="text-sm font-medium text-primary-600 hover:text-primary-500"
            >
              View analytics
            </Link>
          </div>

          {recentEvents.length === 0 ? (
            <div className="text-center py-8">
              <ChartBarIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                No events yet
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Anomaly events will appear here once you upload and process
                videos.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden">
              <ul className="divide-y divide-gray-200">
                {recentEvents.slice(0, 5).map((event) => (
                  <li key={event.id} className="py-4">
                    <div className="flex items-center space-x-4">
                      <div className="flex-shrink-0">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            event.is_alert
                              ? "bg-red-500"
                              : event.anomaly_score > 0.7
                              ? "bg-yellow-500"
                              : "bg-green-500"
                          }`}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">
                          {event.event_type.replace("_", " ").toUpperCase()}
                        </p>
                        <div className="flex items-center space-x-2 text-sm text-gray-500">
                          <span>Score: {event.anomaly_score.toFixed(3)}</span>
                          <span>•</span>
                          <span>
                            Confidence: {(event.confidence * 100).toFixed(1)}%
                          </span>
                          <span>•</span>
                          <span>Frame: {event.frame_number}</span>
                        </div>
                      </div>
                      <div className="flex-shrink-0 text-sm text-gray-500">
                        {new Date(event.created_at).toLocaleTimeString()}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
