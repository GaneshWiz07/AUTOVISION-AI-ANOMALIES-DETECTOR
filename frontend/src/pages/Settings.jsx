import React, { useState, useEffect } from "react";
import { settingsAPI, cleanupAPI } from "./api-utils.js";
import LoadingSpinner from "../components/LoadingSpinner";
import {
  Cog6ToothIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";

const Settings = () => {
  const [settings, setSettings] = useState({
    anomaly_threshold: 0.5,
    frame_sampling_rate: 10,
    auto_delete_old_videos: false,
    video_retention_days: 30,
  });
  const [cleanupPreview, setCleanupPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadSettings();
    loadCleanupPreview();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await settingsAPI.getSettings();
      setSettings(response);
    } catch (err) {
      console.error("Error loading settings:", err);
      setError("Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  const loadCleanupPreview = async () => {
    try {
      const preview = await cleanupAPI.getCleanupPreview();
      setCleanupPreview(preview);
    } catch (err) {
      console.error("Error loading cleanup preview:", err);
    }
  };

  const handleSaveSettings = async () => {
    try {
      setSaving(true);
      setError("");
      setSuccess("");

      await settingsAPI.updateSettings(settings);
      setSuccess("Settings saved successfully!");

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      console.error("Error saving settings:", err);
      setError("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleRunCleanup = async () => {
    if (
      !confirm(
        "Are you sure you want to delete old videos? This action cannot be undone."
      )
    ) {
      return;
    }

    try {
      setCleanupLoading(true);
      const result = await cleanupAPI.runCleanup();
      setSuccess(
        `Cleanup complete: ${
          result.result.videos_deleted
        } videos deleted, ${result.result.space_freed_mb.toFixed(1)}MB freed`
      );

      // Reload cleanup preview
      await loadCleanupPreview();

      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(""), 5000);
    } catch (err) {
      console.error("Error running cleanup:", err);
      setError("Failed to run cleanup");
    } finally {
      setCleanupLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setSettings((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
          <p className="mt-2 text-sm text-gray-700">
            Configure your anomaly detection settings and manage your data.
          </p>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          </div>
        </div>
      )}

      {success && (
        <div className="rounded-md bg-green-50 p-4">
          <div className="flex">
            <CheckCircleIcon className="h-5 w-5 text-green-400" />
            <div className="ml-3">
              <p className="text-sm text-green-800">{success}</p>
            </div>
          </div>
        </div>
      )}

      {/* Anomaly Detection Settings */}
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            <Cog6ToothIcon className="h-5 w-5 inline mr-2" />
            Anomaly Detection Settings
          </h3>

          <div className="space-y-6">
            {/* Anomaly Threshold */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Anomaly Threshold ({settings.anomaly_threshold})
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Higher values = fewer false positives, lower values = more
                sensitive detection
              </p>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={settings.anomaly_threshold}
                onChange={(e) =>
                  handleInputChange(
                    "anomaly_threshold",
                    parseFloat(e.target.value)
                  )
                }
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>More Sensitive (0.0)</span>
                <span>Less Sensitive (1.0)</span>
              </div>
            </div>

            {/* Frame Sampling Rate */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Frame Sampling Rate
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Process every Nth frame (higher = faster processing, lower
                accuracy)
              </p>
              <input
                type="number"
                min="1"
                max="30"
                value={settings.frame_sampling_rate}
                onChange={(e) =>
                  handleInputChange(
                    "frame_sampling_rate",
                    parseInt(e.target.value)
                  )
                }
                className="mt-1 block w-32 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Auto Delete Settings */}
            <div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.auto_delete_old_videos}
                  onChange={(e) =>
                    handleInputChange(
                      "auto_delete_old_videos",
                      e.target.checked
                    )
                  }
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label className="ml-2 block text-sm font-medium text-gray-700">
                  Auto-delete old videos
                </label>
              </div>

              {settings.auto_delete_old_videos && (
                <div className="mt-3 ml-6">
                  <label className="block text-sm font-medium text-gray-700">
                    Delete videos older than (days)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={settings.video_retention_days}
                    onChange={(e) =>
                      handleInputChange(
                        "video_retention_days",
                        parseInt(e.target.value)
                      )
                    }
                    className="mt-1 block w-32 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              )}
            </div>

            {/* Save Button */}
            <div className="pt-4">
              <button
                onClick={handleSaveSettings}
                disabled={saving}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {saving ? <LoadingSpinner size="sm" /> : "Save Settings"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Video Cleanup */}
      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            <TrashIcon className="h-5 w-5 inline mr-2" />
            Video Cleanup
          </h3>

          {cleanupPreview && (
            <div className="space-y-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Videos to delete:</span>
                    <span className="ml-2">
                      {cleanupPreview.videos_to_delete}
                    </span>
                  </div>
                  <div>
                    <span className="font-medium">Space to free:</span>
                    <span className="ml-2">
                      {cleanupPreview.space_to_free_mb} MB
                    </span>
                  </div>
                </div>
                {cleanupPreview.cutoff_date && (
                  <p className="text-sm text-gray-600 mt-2">
                    Videos older than{" "}
                    {new Date(cleanupPreview.cutoff_date).toLocaleDateString()}{" "}
                    will be deleted
                  </p>
                )}
              </div>

              <button
                onClick={handleRunCleanup}
                disabled={
                  cleanupLoading || cleanupPreview.videos_to_delete === 0
                }
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                {cleanupLoading ? <LoadingSpinner size="sm" /> : "Run Cleanup"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Settings;
