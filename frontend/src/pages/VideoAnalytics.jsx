import React, { useState, useEffect } from "react";
import { videoAPI, eventAPI } from "./api-utils.js";
import AnomalyChart from "../components/AnomalyChart";
import LoadingSpinner from "../components/LoadingSpinner";
import {
  PlayIcon,
  TrashIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
} from "@heroicons/react/24/outline";

const VideoAnalytics = () => {
  const [videos, setVideos] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [processingVideo, setProcessingVideo] = useState(null);
  const [showVideoPopup, setShowVideoPopup] = useState(false);
  useEffect(() => {
    loadData();

    // Set up polling for videos that are processing
    const pollInterval = setInterval(async () => {
      try {
        const videosData = await videoAPI.getVideos(50);
        const processingVideos =
          videosData.videos?.filter((v) => v.upload_status === "processing") ||
          [];

        if (processingVideos.length > 0) {
          // Refresh data if there are processing videos
          loadData();
        }
      } catch (error) {
        // Ignore polling errors to avoid spam
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, []);

  // Handle ESC key to close video popup
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && showVideoPopup) {
        handleCloseVideoPopup();
      }
    };

    if (showVideoPopup) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [showVideoPopup]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [videosResponse, eventsResponse] = await Promise.all([
        videoAPI.getVideos(50),
        eventAPI.getEvents(100),
      ]);

      setVideos(videosResponse.videos || []);
      setEvents(eventsResponse.events || []);
    } catch (err) {
      console.error("Error loading analytics data:", err);
      setError("Failed to load analytics data");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVideo = async (videoId) => {
    if (!confirm("Are you sure you want to delete this video?")) return;

    try {
      await videoAPI.deleteVideo(videoId);
      setVideos(videos.filter((v) => v.id !== videoId));
      setEvents(events.filter((e) => e.video_id !== videoId));
      if (selectedVideo?.id === videoId) {
        setSelectedVideo(null);
      }
    } catch (err) {
      console.error("Error deleting video:", err);
      alert("Failed to delete video");
    }
  };

  const handleProcessVideo = async (videoId) => {
    try {
      setProcessingVideo(videoId);
      await videoAPI.processVideo(videoId);
      // Reload data to get updated events
      await loadData();
    } catch (err) {
      console.error("Error processing video:", err);
      alert("Failed to process video");
    } finally {
      setProcessingVideo(null);
    }
  };

  const handlePlayVideo = async (videoId) => {
    try {
      const video = videos.find((v) => v.id === videoId);
      if (!video) {
        alert("Video not found");
        return;
      }

      if (video.upload_status !== "completed") {
        alert(
          "Video is still processing. Please wait until processing is complete."
        );
        return;
      }

      setSelectedVideo(video);
      setShowVideoPopup(true);
    } catch (err) {
      console.error("Error playing video:", err);
      alert("Failed to play video. Please try again.");
    }
  };

  const handleCloseVideoPopup = () => {
    setSelectedVideo(null);
    setShowVideoPopup(false);
  };

  const getVideoStreamUrl = (videoId) => {
    // First check if we have the video's direct URL in our state
    const video = videos.find((v) => v.id === videoId);

    // If video has a storage URL from Supabase Storage, use it directly
    if (video?.file_url && video.storage_provider === "supabase") {
      return video.file_url;
    }

    // Otherwise fall back to the backend streaming endpoint
    return videoAPI.getVideoStreamUrl(videoId);
  };

  const formatFileSize = (bytes) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  const getVideoEvents = (videoId) => {
    return events.filter((event) => event.video_id === videoId);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "completed":
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case "failed":
        return <XCircleIcon className="h-5 w-5 text-red-500" />;
      case "processing":
        return <LoadingSpinner size="sm" />;
      default:
        return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-red-500" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">Error</h3>
        <p className="mt-1 text-sm text-gray-500">{error}</p>
        <button
          onClick={loadData}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">
            Video Analytics
          </h1>
          <p className="mt-2 text-sm text-gray-700">
            Analyze your uploaded videos and view anomaly detection results.
          </p>
        </div>
      </div>

      {/* Video List */}
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Uploaded Videos ({videos.length})
          </h3>

          {videos.length === 0 ? (
            <div className="text-center py-8">
              <PlayIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">
                No videos
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Upload a video to get started with anomaly detection.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {videos.map((video) => {
                const videoEvents = getVideoEvents(video.id);
                const anomalyCount = videoEvents.filter(
                  (e) => e.is_alert
                ).length;

                return (
                  <div
                    key={video.id}
                    className="border rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedVideo(video)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3">
                          {getStatusIcon(video.upload_status)}
                          <div>
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {video.original_name}
                            </p>
                            <p className="text-sm text-gray-500">
                              {video.duration_seconds
                                ? `${Math.round(video.duration_seconds)}s`
                                : "Duration unknown"}
                              {video.resolution && ` • ${video.resolution}`}
                              {video.file_size &&
                                ` • ${(video.file_size / 1024 / 1024).toFixed(
                                  1
                                )}MB`}
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-4">
                        {anomalyCount > 0 && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            {anomalyCount} anomalies
                          </span>
                        )}{" "}
                        {video.upload_status === "completed" && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePlayVideo(video.id);
                              }}
                              className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md text-green-700 bg-green-100 hover:bg-green-200"
                              title="Play Video"
                            >
                              <PlayIcon className="h-4 w-4 mr-1" />
                              Play
                            </button>

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleProcessVideo(video.id);
                              }}
                              disabled={processingVideo === video.id}
                              className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200 disabled:opacity-50"
                            >
                              {processingVideo === video.id ? (
                                <LoadingSpinner size="sm" />
                              ) : (
                                "Reprocess"
                              )}
                            </button>
                          </>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteVideo(video.id);
                          }}
                          className="inline-flex items-center p-1 border border-transparent rounded-full text-red-400 hover:text-red-600 hover:bg-red-50"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Selected Video Details */}
      {selectedVideo && (
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
              Video Analysis: {selectedVideo.original_name}
            </h3>
            <div className="space-y-6">
              {/* Events Chart */}
              {getVideoEvents(selectedVideo.id).length > 0 ? (
                <div>
                  <h4 className="text-md font-medium text-gray-900 mb-3">
                    Anomaly Timeline
                  </h4>
                  <AnomalyChart events={getVideoEvents(selectedVideo.id)} />
                </div>
              ) : (
                <div className="text-center py-8">
                  <CheckCircleIcon className="mx-auto h-12 w-12 text-green-500" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    No anomalies detected
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    This video appears to be normal.
                  </p>
                </div>
              )}

              {/* Events List */}
              {getVideoEvents(selectedVideo.id).length > 0 && (
                <div>
                  <h4 className="text-md font-medium text-gray-900 mb-3">
                    Detected Events
                  </h4>
                  <div className="space-y-2">
                    {getVideoEvents(selectedVideo.id).map((event) => (
                      <div
                        key={event.id}
                        className={`p-3 rounded-lg border ${
                          event.is_alert
                            ? "border-red-200 bg-red-50"
                            : "border-gray-200 bg-gray-50"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium text-gray-900">
                              {event.event_type || "Anomaly"}
                            </p>
                            <p className="text-sm text-gray-500">
                              At {Math.round(event.timestamp_seconds)}s •
                              Confidence: {(event.confidence * 100).toFixed(1)}%
                              • Score: {event.anomaly_score.toFixed(2)}
                            </p>
                            {event.description && (
                              <p className="text-sm text-gray-600 mt-1">
                                {event.description}
                              </p>
                            )}
                          </div>
                          {event.is_alert && (
                            <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>{" "}
          </div>
        </div>
      )}

      {/* Simple Video Popup */}
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
              </div>

              {/* Video player */}
              <div className="relative bg-black rounded-lg overflow-hidden shadow-inner">
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
