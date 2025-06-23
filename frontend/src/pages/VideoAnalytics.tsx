import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import VideoUpload from "../components/VideoUpload";
import AnomalyChart from "../components/AnomalyChart";
import LoadingSpinner from "../components/LoadingSpinner";
import {
  videoAPI,
  eventAPI,
  settingsAPI,
  cleanupAPI,
  Video as APIVideo,
  Event as APIEvent,
  UserSettings,
} from "../lib/api.ts";
import {
  PlayIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ChartBarIcon,
  EyeIcon,
  TrashIcon,
  CloudArrowUpIcon,
  VideoCameraIcon,
  HomeIcon,
  CogIcon,
} from "@heroicons/react/24/outline";

// Use API types directly
type Video = APIVideo;
type Event = APIEvent;

interface AnalyticsData {
  total_videos: number;
  total_events: number;
  total_alerts: number;
  avg_anomaly_score: number;
  processing_videos: number;
  recent_activity: Event[];
}

const VideoAnalytics: React.FC = () => {
  const location = useLocation();
  const [videos, setVideos] = useState<Video[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Settings state
  const [settings, setSettings] = useState<UserSettings>({
    anomaly_threshold: 0.5,
    frame_sampling_rate: 10,
    auto_delete_old_videos: false,
    video_retention_days: 30,
  });
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  // Cleanup state
  const [cleanupPreview, setCleanupPreview] = useState<any>(null);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [showCleanupPreview, setShowCleanupPreview] = useState(false);

  // Video popup state
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [showVideoPopup, setShowVideoPopup] = useState(false);

  // Determine initial tab based on route
  const getInitialTab = () => {
    if (location.pathname === "/settings") return "settings";
    if (location.pathname === "/analytics") return "analytics";
    return "dashboard";
  };

  const [activeTab, setActiveTab] = useState<
    "dashboard" | "analytics" | "settings"
  >(getInitialTab());
  useEffect(() => {
    fetchData();

    // Set up polling for videos that are processing
    const pollInterval = setInterval(async () => {
      try {
        const videosData = await videoAPI.getVideos();
        const processingVideos =
          videosData.videos?.filter(
            (v: APIVideo) => v.upload_status === "processing"
          ) || [];

        if (processingVideos.length > 0) {
          // Refresh data if there are processing videos
          fetchData();
        }
      } catch (error) {
        // Ignore polling errors
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, []);

  // Update active tab when route changes
  useEffect(() => {
    setActiveTab(getInitialTab());
  }, [location.pathname]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [videosData, eventsData] = await Promise.all([
        videoAPI.getVideos(),
        eventAPI.getEvents(),
      ]);

      setVideos(videosData.videos || []);
      setEvents(eventsData.events || []); // Calculate analytics
      const analyticsData: AnalyticsData = {
        total_videos: videosData.videos?.length || 0,
        total_events: eventsData.events?.length || 0,
        total_alerts:
          eventsData.events?.filter((e: APIEvent) => e.is_alert).length || 0,
        avg_anomaly_score: eventsData.events?.length
          ? eventsData.events.reduce(
              (sum: number, e: APIEvent) => sum + e.anomaly_score,
              0
            ) / eventsData.events.length
          : 0,
        processing_videos:
          videosData.videos?.filter(
            (v: APIVideo) => v.upload_status === "processing"
          ).length || 0,
        recent_activity: eventsData.events?.slice(0, 10) || [],
      };

      setAnalytics(analyticsData);
    } catch (err: any) {
      setError(err.message || "Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };
  const handleUploadSuccess = (videoData: any) => {
    // Transform the upload result to match the Video interface
    const transformedVideo: Video = {
      id: videoData.video_id,
      filename: videoData.filename,
      original_name: videoData.original_name,
      file_path: "",
      file_size: videoData.metadata?.file_size || 0,
      duration_seconds: videoData.metadata?.duration,
      fps: videoData.metadata?.fps,
      resolution: videoData.metadata?.resolution,
      upload_status: videoData.status || "completed",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setVideos((prev) => [transformedVideo, ...prev]);
    fetchData(); // Refresh all data
  };

  const handleDeleteVideo = async (videoId: string) => {
    if (!window.confirm("Are you sure you want to delete this video?")) return;

    try {
      console.log("Attempting to delete video with ID:", videoId);
      await videoAPI.deleteVideo(videoId);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
      setEvents((prev) => prev.filter((e) => e.video_id !== videoId));
      console.log("Video deleted successfully:", videoId);

      // Refresh analytics data after deletion
      fetchData();
    } catch (err: any) {
      console.error("Delete video error:", err);
      setError(err.message || "Failed to delete video");
    }
  };
  const handlePlayVideo = (video: Video) => {
    setSelectedVideo(video);
    setShowVideoPopup(true);
  };

  const handleCloseVideoPopup = () => {
    setSelectedVideo(null);
    setShowVideoPopup(false);
  }; // Get video stream URL with auth token or direct storage URL
  const getVideoStreamUrl = (videoId: string) => {
    // First check if we have the video's direct URL in our state
    const video = videos.find((v) => v.id === videoId);

    // If video has a storage URL from Supabase Storage, use it directly
    if (video?.file_url && video.storage_provider === "supabase") {
      return video.file_url;
    }

    // Otherwise fall back to the backend streaming endpoint
    const token = localStorage.getItem("access_token");
    // Use the same base URL as the API, which already includes /api/v1
    const baseUrl =
      import.meta.env.VITE_API_URL || "http://localhost:12000/api/v1";
    return `${baseUrl}/videos/${videoId}/stream?token=${token}`;
  };

  // Handle escape key to close video popup
  useEffect(() => {
    const handleEscapeKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && showVideoPopup) {
        handleCloseVideoPopup();
      }
    };

    if (showVideoPopup) {
      document.addEventListener("keydown", handleEscapeKey);
      return () => {
        document.removeEventListener("keydown", handleEscapeKey);
      };
    }
  }, [showVideoPopup]);
  const formatFileSize = (bytes: number) => {
    const sizes = ["Bytes", "KB", "MB", "GB"];
    if (bytes === 0) return "0 Bytes";
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-green-600 bg-green-100";
      case "processing":
        return "text-yellow-600 bg-yellow-100";
      case "failed":
        return "text-red-600 bg-red-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };
  const getSeverityColor = (anomalyScore: number) => {
    if (anomalyScore >= 0.8) return "text-red-600 bg-red-100";
    if (anomalyScore >= 0.6) return "text-orange-600 bg-orange-100";
    if (anomalyScore >= 0.4) return "text-yellow-600 bg-yellow-100";
    return "text-green-600 bg-green-100";
  };

  // Settings functions
  const fetchSettings = async () => {
    try {
      setSettingsLoading(true);
      const userSettings = await settingsAPI.getSettings();
      setSettings(userSettings);
    } catch (err: any) {
      console.error("Error fetching settings:", err);
      // Keep default settings on error
    } finally {
      setSettingsLoading(false);
    }
  };

  const updateSetting = async (key: keyof UserSettings, value: any) => {
    try {
      setSettingsLoading(true);
      const updatedSettings = await settingsAPI.updateSettings({
        [key]: value,
      });
      setSettings(updatedSettings);
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 2000);
    } catch (err: any) {
      console.error("Error updating setting:", err);
      console.error("Error details:", {
        status: err.response?.status,
        statusText: err.response?.statusText,
        data: err.response?.data,
        message: err.message,
      });
      setError(
        err.response?.data?.detail || err.message || "Failed to update setting"
      );
    } finally {
      setSettingsLoading(false);
    }
  };

  // Load settings when component mounts or when switching to settings tab
  useEffect(() => {
    if (activeTab === "settings") {
      fetchSettings();
    }
  }, [activeTab]);

  // Cleanup functions
  const fetchCleanupPreview = async () => {
    try {
      setCleanupLoading(true);
      const preview = await cleanupAPI.getCleanupPreview();
      setCleanupPreview(preview);
    } catch (err: any) {
      console.error("Error fetching cleanup preview:", err);
      setError(err.response?.data?.detail || "Failed to fetch cleanup preview");
    } finally {
      setCleanupLoading(false);
    }
  };

  const runVideoCleanup = async () => {
    if (
      !window.confirm(
        "Are you sure you want to delete old videos? This action cannot be undone."
      )
    ) {
      return;
    }

    try {
      setCleanupLoading(true);
      const result = await cleanupAPI.runCleanup();

      // Show success message
      alert(result.message);

      // Refresh data
      fetchData();
      setShowCleanupPreview(false);
      setCleanupPreview(null);
    } catch (err: any) {
      console.error("Error running cleanup:", err);
      setError(err.response?.data?.detail || "Failed to run cleanup");
    } finally {
      setCleanupLoading(false);
    }
  };
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        {" "}
        <div className="text-center">
          <LoadingSpinner size="lg" className="mx-auto" />
          <p className="mt-4 text-lg font-medium text-gray-900">
            Loading AutoVision Dashboard...
          </p>
          <p className="mt-2 text-sm text-gray-500">
            Initializing AI surveillance analytics
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {" "}
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center space-x-4">
            <div className="h-12 w-12 flex items-center justify-center rounded-lg bg-blue-100 border-2 border-blue-200">
              <svg
                className="h-6 w-6 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
                <circle
                  cx="8"
                  cy="12"
                  r="2"
                  stroke="currentColor"
                  strokeWidth={2}
                  fill="none"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                AutoVision Dashboard
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                AI-Powered Video Surveillance & Anomaly Detection Platform
              </p>
            </div>
          </div>
        </div>
        {/* Error Alert */}
        {error && (
          <div className="mb-6 rounded-md bg-red-50 p-4">
            <div className="flex">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
              <button
                onClick={() => setError("")}
                className="ml-auto text-red-400 hover:text-red-600"
              >
                ×
              </button>
            </div>
          </div>
        )}
        {/* Tabs */}
        <div className="mb-6">
          <nav className="flex space-x-8">
            {" "}
            {[
              { id: "dashboard", name: "Dashboard", icon: HomeIcon },
              { id: "analytics", name: "Analytics", icon: ChartBarIcon },
              { id: "settings", name: "Settings", icon: CogIcon },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                  activeTab === tab.id
                    ? "bg-primary-100 text-primary-700"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <tab.icon className="h-5 w-5 mr-2" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>{" "}
        {/* Tab Content */}
        <div className="bg-white shadow rounded-lg">
          {activeTab === "dashboard" && (
            <div className="p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-6">
                Dashboard Overview
              </h2>

              {/* Quick Stats */}
              {analytics && (
                <div className="mb-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="bg-gradient-to-r from-blue-500 to-blue-600 overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <DocumentTextIcon className="h-6 w-6 text-white" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-blue-100 truncate">
                              Total Videos
                            </dt>
                            <dd className="text-lg font-medium text-white">
                              {analytics.total_videos}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-green-500 to-green-600 overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <EyeIcon className="h-6 w-6 text-white" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-green-100 truncate">
                              Events Detected
                            </dt>
                            <dd className="text-lg font-medium text-white">
                              {analytics.total_events}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-red-500 to-red-600 overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <ExclamationTriangleIcon className="h-6 w-6 text-white" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-red-100 truncate">
                              Critical Alerts
                            </dt>
                            <dd className="text-lg font-medium text-white">
                              {analytics.total_alerts}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-purple-500 to-purple-600 overflow-hidden shadow rounded-lg">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <ChartBarIcon className="h-6 w-6 text-white" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-purple-100 truncate">
                              Avg Score
                            </dt>
                            <dd className="text-lg font-medium text-white">
                              {(analytics.avg_anomaly_score * 100).toFixed(1)}%
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Video Upload Section */}
              <div className="mb-8">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Upload New Video
                </h3>
                <VideoUpload
                  onUploadSuccess={handleUploadSuccess}
                  onUploadError={setError}
                />
              </div>

              {/* Recent Videos Summary */}
              <div className="mb-8">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Recent Videos ({videos.length})
                </h3>
                {videos.length === 0 ? (
                  <div className="text-center py-8 bg-gray-50 rounded-lg">
                    <VideoCameraIcon className="mx-auto h-12 w-12 text-gray-400" />
                    <h4 className="mt-2 text-sm font-medium text-gray-900">
                      No videos uploaded yet
                    </h4>
                    <p className="mt-1 text-sm text-gray-500">
                      Start by uploading your first video above.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {videos.slice(0, 3).map((video) => (
                      <div
                        key={video.id}
                        className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center">
                          <VideoCameraIcon className="h-8 w-8 text-gray-400" />
                          <div className="ml-3">
                            <div className="text-sm font-medium text-gray-900">
                              {video.original_name}
                            </div>
                            <div className="text-sm text-gray-500">
                              {formatFileSize(video.file_size)} •{" "}
                              {new Date(video.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>{" "}
                        <div className="flex items-center space-x-2">
                          <span
                            className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(
                              video.upload_status
                            )}`}
                          >
                            {video.upload_status}{" "}
                          </span>{" "}
                          <button
                            onClick={() => handlePlayVideo(video)}
                            className="text-blue-600 hover:text-blue-900"
                            title="Play video"
                          >
                            <PlayIcon className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteVideo(video.id)}
                            className="text-red-600 hover:text-red-900"
                            title="Delete video"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                    {videos.length > 3 && (
                      <div className="text-center py-2">
                        <span className="text-sm text-gray-500">
                          Showing 3 of {videos.length} videos
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Recent Events Summary */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Recent Events ({events.length})
                </h3>{" "}
                {events.length === 0 ? (
                  <div className="text-center py-8 bg-gray-50 rounded-lg">
                    <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-gray-400" />
                    <h4 className="mt-2 text-sm font-medium text-gray-900">
                      No events detected yet
                    </h4>{" "}
                    <p className="mt-1 text-sm text-gray-500">
                      {videos.some((v) => v.upload_status === "uploaded")
                        ? "Your uploaded videos are automatically processed for AI analysis and anomaly detection."
                        : "Upload videos to see automatic anomaly detection results."}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {events.slice(0, 3).map((event) => (
                      <div
                        key={event.id}
                        className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center space-x-3">
                          <div
                            className={`w-3 h-3 rounded-full ${
                              event.is_alert ? "bg-red-500" : "bg-yellow-500"
                            }`}
                          ></div>
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {event.event_type}
                            </div>
                            <div className="text-xs text-gray-500">
                              Frame {event.frame_number} •{" "}
                              {event.timestamp_seconds.toFixed(1)}s
                            </div>
                          </div>
                        </div>
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(
                            event.anomaly_score
                          )}`}
                        >
                          {(event.anomaly_score * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                    {events.length > 3 && (
                      <div className="text-center py-2">
                        <span className="text-sm text-gray-500">
                          Showing 3 of {events.length} events
                        </span>
                      </div>
                    )}
                  </div>
                )}{" "}
              </div>
            </div>
          )}{" "}
          {activeTab === "analytics" && (
            <div className="p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-6">
                Analytics Dashboard
              </h2>

              {/* Analytics Overview Cards */}
              {analytics && (
                <div className="mb-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="bg-white overflow-hidden shadow-lg rounded-lg border border-gray-200">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <DocumentTextIcon className="h-8 w-8 text-blue-500" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-gray-500 truncate">
                              Total Videos
                            </dt>
                            <dd className="text-2xl font-bold text-gray-900">
                              {analytics.total_videos}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white overflow-hidden shadow-lg rounded-lg border border-gray-200">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <EyeIcon className="h-8 w-8 text-green-500" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-gray-500 truncate">
                              Total Events
                            </dt>
                            <dd className="text-2xl font-bold text-gray-900">
                              {analytics.total_events}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white overflow-hidden shadow-lg rounded-lg border border-gray-200">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <ExclamationTriangleIcon className="h-8 w-8 text-red-500" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-gray-500 truncate">
                              Critical Alerts
                            </dt>
                            <dd className="text-2xl font-bold text-red-600">
                              {analytics.total_alerts}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white overflow-hidden shadow-lg rounded-lg border border-gray-200">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <ChartBarIcon className="h-8 w-8 text-purple-500" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-gray-500 truncate">
                              Avg Anomaly Score
                            </dt>
                            <dd className="text-2xl font-bold text-gray-900">
                              {(analytics.avg_anomaly_score * 100).toFixed(1)}%
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white overflow-hidden shadow-lg rounded-lg border border-gray-200">
                    <div className="p-5">
                      <div className="flex items-center">
                        <div className="flex-shrink-0">
                          <PlayIcon className="h-8 w-8 text-yellow-500" />
                        </div>
                        <div className="ml-5 w-0 flex-1">
                          <dl>
                            <dt className="text-sm font-medium text-gray-500 truncate">
                              Processing
                            </dt>
                            <dd className="text-2xl font-bold text-yellow-600">
                              {analytics.processing_videos}
                            </dd>
                          </dl>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Analytics Content */}
              {analytics && events.length > 0 ? (
                <div className="space-y-8">
                  {/* Anomaly Chart Section */}
                  <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
                    <h3 className="text-xl font-semibold text-gray-900 mb-4">
                      Anomaly Detection Trends
                    </h3>
                    <AnomalyChart events={events} />
                  </div>

                  {/* Analytics Grid */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Recent Activity */}
                    <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
                      <h3 className="text-lg font-semibold text-gray-900 mb-4">
                        Recent Activity
                      </h3>
                      <div className="space-y-4">
                        {analytics.recent_activity.slice(0, 5).map((event) => (
                          <div
                            key={event.id}
                            className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg border"
                          >
                            <div className="flex items-center space-x-3">
                              <div
                                className={`w-3 h-3 rounded-full ${
                                  event.is_alert
                                    ? "bg-red-500"
                                    : "bg-yellow-500"
                                }`}
                              ></div>
                              <div>
                                <span className="text-sm font-medium text-gray-900">
                                  {event.event_type}
                                </span>
                                <div className="text-xs text-gray-500">
                                  {(event.anomaly_score * 100).toFixed(1)}%
                                  confidence
                                </div>
                              </div>
                            </div>
                            <span className="text-xs text-gray-500">
                              {new Date(event.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Event Type Distribution */}
                    <div className="bg-white p-6 rounded-lg shadow border border-gray-200">
                      <h3 className="text-lg font-semibold text-gray-900 mb-4">
                        Event Type Distribution
                      </h3>
                      <div className="space-y-3">
                        {" "}
                        {Object.entries(
                          events.reduce((acc, event) => {
                            acc[event.event_type] =
                              (acc[event.event_type] || 0) + 1;
                            return acc;
                          }, {} as Record<string, number>)
                        ).map(([eventType, count]) => (
                          <div
                            key={eventType}
                            className="flex items-center justify-between"
                          >
                            <span className="text-sm font-medium text-gray-700">
                              {eventType}
                            </span>
                            <div className="flex items-center space-x-2">
                              <div className="w-20 bg-gray-200 rounded-full h-2 relative">
                                <div
                                  className={`bg-blue-500 h-2 rounded-full absolute left-0 top-0 ${
                                    (count as number) / events.length > 0.75
                                      ? "w-full"
                                      : (count as number) / events.length > 0.5
                                      ? "w-3/4"
                                      : (count as number) / events.length > 0.25
                                      ? "w-1/2"
                                      : (count as number) / events.length > 0.1
                                      ? "w-1/4"
                                      : "w-1/12"
                                  }`}
                                ></div>
                              </div>
                              <span className="text-sm text-gray-500 w-8">
                                {count as number}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Alert Summary */}
                  {analytics.total_alerts > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-red-900 mb-4">
                        Alert Summary
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-red-600">
                            {
                              events.filter(
                                (e) => e.is_alert && e.anomaly_score >= 0.8
                              ).length
                            }
                          </div>
                          <div className="text-sm text-red-700">
                            High Priority
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-orange-600">
                            {
                              events.filter(
                                (e) =>
                                  e.is_alert &&
                                  e.anomaly_score >= 0.6 &&
                                  e.anomaly_score < 0.8
                              ).length
                            }
                          </div>
                          <div className="text-sm text-orange-700">
                            Medium Priority
                          </div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-yellow-600">
                            {
                              events.filter(
                                (e) => e.is_alert && e.anomaly_score < 0.6
                              ).length
                            }
                          </div>
                          <div className="text-sm text-yellow-700">
                            Low Priority
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-16 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                  <ChartBarIcon className="mx-auto h-16 w-16 text-gray-400" />
                  <h3 className="mt-4 text-lg font-medium text-gray-900">
                    No Analytics Data Available
                  </h3>{" "}
                  <p className="mt-2 text-sm text-gray-500 max-w-sm mx-auto">
                    {videos.some((v) => v.upload_status === "uploaded")
                      ? "Your uploaded videos are automatically processed to generate comprehensive analytics and anomaly detection results."
                      : "Upload videos and let our AI automatically process them to see comprehensive analytics and anomaly detection results here."}
                  </p>{" "}
                  <div className="mt-6">
                    <button
                      onClick={() => setActiveTab("dashboard")}
                      className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
                    >
                      <CloudArrowUpIcon className="h-5 w-5 mr-2" />
                      Upload Your First Video
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {activeTab === "settings" && (
            <div className="p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-6">
                Settings
              </h2>{" "}
              {settingsSaved && (
                <div className="mb-4 rounded-md bg-green-50 p-4">
                  <div className="flex">
                    <div className="text-sm text-green-700">
                      Settings saved successfully!
                    </div>
                  </div>
                </div>
              )}
              {/* Detection Settings */}
              <div className="mb-8">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Detection Settings
                </h3>
                <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                  <div>
                    <label
                      htmlFor="anomaly-threshold"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Anomaly Detection Threshold:{" "}
                      {settings.anomaly_threshold.toFixed(1)}
                    </label>
                    <input
                      id="anomaly-threshold"
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={settings.anomaly_threshold}
                      onChange={(e) =>
                        updateSetting(
                          "anomaly_threshold",
                          parseFloat(e.target.value)
                        )
                      }
                      disabled={settingsLoading}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                      aria-label="Anomaly Detection Threshold"
                    />
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>Low Sensitivity</span>
                      <span>High Sensitivity</span>
                    </div>
                  </div>
                  <div>
                    <label
                      htmlFor="frame-sampling-rate"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Frame Sampling Rate
                    </label>
                    <select
                      id="frame-sampling-rate"
                      value={settings.frame_sampling_rate}
                      onChange={(e) =>
                        updateSetting(
                          "frame_sampling_rate",
                          parseInt(e.target.value)
                        )
                      }
                      disabled={settingsLoading}
                      className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50"
                      aria-label="Frame Sampling Rate"
                    >
                      <option value="1">Every Frame</option>
                      <option value="5">Every 5th Frame</option>
                      <option value="10">Every 10th Frame</option>
                      <option value="30">Every 30th Frame</option>
                    </select>
                  </div>
                </div>{" "}
              </div>
              {/* System Settings */}
              <div className="mb-8">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  System Settings
                </h3>
                <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-gray-700">
                      Auto-delete Old Videos
                    </label>
                    <button
                      onClick={() =>
                        updateSetting(
                          "auto_delete_old_videos",
                          !settings.auto_delete_old_videos
                        )
                      }
                      disabled={settingsLoading}
                      className={`relative inline-flex flex-shrink-0 h-6 w-11 border-2 border-transparent rounded-full cursor-pointer transition-colors ease-in-out duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 ${
                        settings.auto_delete_old_videos
                          ? "bg-primary-600"
                          : "bg-gray-200"
                      }`}
                    >
                      <span className="sr-only">Auto-delete old videos</span>
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transform ring-0 transition ease-in-out duration-200 ${
                          settings.auto_delete_old_videos
                            ? "translate-x-5"
                            : "translate-x-0"
                        }`}
                      ></span>
                    </button>
                  </div>
                  <div>
                    <label
                      htmlFor="video-retention-days"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Video Retention Period (days)
                    </label>
                    <input
                      id="video-retention-days"
                      type="number"
                      min="1"
                      max="365"
                      value={settings.video_retention_days}
                      onChange={(e) =>
                        updateSetting(
                          "video_retention_days",
                          parseInt(e.target.value)
                        )
                      }
                      disabled={settingsLoading}
                      className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50"
                      aria-label="Video Retention Days"
                    />{" "}
                  </div>
                </div>
              </div>
              {/* Cleanup Settings */}
              <div className="mb-8">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Cleanup Settings
                </h3>
                <div className="bg-gray-50 rounded-lg p-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Video Cleanup Preview
                    </label>
                    <button
                      onClick={fetchCleanupPreview}
                      disabled={cleanupLoading}
                      className="w-full inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                    >
                      {" "}
                      {cleanupLoading ? (
                        <LoadingSpinner size="sm" className="mr-2" />
                      ) : null}
                      {showCleanupPreview ? "Refresh Preview" : "Show Preview"}
                    </button>
                  </div>{" "}
                  {cleanupPreview && (
                    <div className="bg-white rounded-lg p-4 shadow">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">
                        Cleanup Preview
                      </h4>
                      {cleanupPreview.videos_to_delete > 0 ? (
                        <>
                          <div className="mb-4 p-3 bg-yellow-50 rounded-lg">
                            <p className="text-sm text-yellow-800">
                              <strong>{cleanupPreview.videos_to_delete}</strong>{" "}
                              videos will be deleted, freeing{" "}
                              <strong>
                                {cleanupPreview.space_to_free_mb} MB
                              </strong>{" "}
                              of storage space.
                            </p>
                            <p className="text-xs text-yellow-600 mt-1">
                              Videos older than {cleanupPreview.retention_days}{" "}
                              days will be removed.
                            </p>
                          </div>
                          {cleanupPreview.videos && (
                            <div className="space-y-2 max-h-40 overflow-y-auto mb-4">
                              {cleanupPreview.videos.map((video: any) => (
                                <div
                                  key={video.id}
                                  className="flex justify-between items-center p-2 bg-gray-50 rounded"
                                >
                                  <div>
                                    <span className="text-sm font-medium">
                                      {video.name}
                                    </span>
                                    <div className="text-xs text-gray-500">
                                      {video.size_mb} MB •{" "}
                                      {new Date(
                                        video.created_at
                                      ).toLocaleDateString()}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                          <button
                            onClick={runVideoCleanup}
                            disabled={cleanupLoading}
                            className="w-full inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
                          >
                            {" "}
                            {cleanupLoading ? (
                              <LoadingSpinner size="sm" className="mr-2" />
                            ) : (
                              <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
                            )}
                            Delete Old Videos
                          </button>
                        </>
                      ) : (
                        <div className="p-3 bg-green-50 rounded-lg">
                          <p className="text-sm text-green-800">
                            {cleanupPreview.message ||
                              "No videos to delete based on current retention settings."}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}{" "}
        </div>
      </div>
      {/* Video Popup Modal */}
      {showVideoPopup && selectedVideo && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:block sm:p-0">
            {/* Background overlay */}
            <div
              className="fixed inset-0 transition-opacity bg-gray-500 bg-opacity-75"
              onClick={handleCloseVideoPopup}
            ></div>

            {/* Modal content */}
            <div className="inline-block w-full max-w-4xl p-6 my-8 overflow-hidden text-left align-middle transition-all transform bg-white shadow-xl rounded-lg">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900 truncate pr-4">
                  {selectedVideo.original_name}
                </h3>
                <button
                  onClick={handleCloseVideoPopup}
                  className="flex-shrink-0 text-gray-400 hover:text-gray-600 focus:outline-none focus:text-gray-600 transition ease-in-out duration-150"
                  aria-label="Close video player"
                >
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>{" "}
              {/* Video player */}
              <div className="relative bg-black rounded-lg overflow-hidden shadow-inner">
                {" "}
                <video
                  controls
                  className="w-full h-auto max-h-96"
                  src={getVideoStreamUrl(selectedVideo.id)}
                  preload="metadata"
                >
                  Your browser does not support the video tag.
                </video>
              </div>
              {/* Video info */}
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600">
                  <div className="flex items-center">
                    <svg
                      className="h-4 w-4 mr-1 text-gray-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2m-9 0h10m-10 0a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V6a2 2 0 00-2-2"
                      />
                    </svg>
                    <span className="font-medium">
                      {formatFileSize(selectedVideo.file_size)}
                    </span>
                  </div>
                  {selectedVideo.duration_seconds && (
                    <div className="flex items-center">
                      <svg
                        className="h-4 w-4 mr-1 text-gray-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <span>{Math.round(selectedVideo.duration_seconds)}s</span>
                    </div>
                  )}
                  {selectedVideo.resolution && (
                    <div className="flex items-center">
                      <svg
                        className="h-4 w-4 mr-1 text-gray-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h10a2 2 0 012 2v14a2 2 0 01-2 2z"
                        />
                      </svg>
                      <span>{selectedVideo.resolution}</span>
                    </div>
                  )}
                  <div className="flex items-center">
                    <svg
                      className="h-4 w-4 mr-1 text-gray-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                    <span>
                      Uploaded:{" "}
                      {new Date(selectedVideo.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  Press ESC to close this video player
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoAnalytics;
