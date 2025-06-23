import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { videoAPI } from "../lib/api.js";
import { CloudArrowUpIcon, CheckCircleIcon } from "@heroicons/react/24/outline";

const VideoUpload = ({ onUploadSuccess, onUploadError }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles) => {
      const file = acceptedFiles[0];
      if (!file) return;

      // Validate file type
      if (!file.type.startsWith("video/")) {
        onUploadError?.("Please select a video file");
        return;
      }

      // Validate file size (100MB limit)
      const maxSize = 100 * 1024 * 1024;
      if (file.size > maxSize) {
        onUploadError?.("File size must be less than 100MB");
        return;
      }

      setUploading(true);
      setUploadProgress(0);

      try {
        // Simulate upload progress
        const progressInterval = setInterval(() => {
          setUploadProgress((prev) => {
            if (prev >= 90) {
              clearInterval(progressInterval);
              return 90;
            }
            return prev + 10;
          });
        }, 200);

        const result = await videoAPI.uploadVideo(file);

        clearInterval(progressInterval);
        setUploadProgress(100);
        setUploadSuccess(true);

        // Always auto-process uploaded videos
        try {
          await videoAPI.processVideo(result.video_id);
        } catch (processError) {
          console.warn("Auto-processing failed:", processError);
        }

        setTimeout(() => {
          setUploading(false);
          setUploadProgress(0);
          setUploadSuccess(false);
          onUploadSuccess?.(result);
        }, 2000);
      } catch (error) {
        setUploading(false);
        setUploadProgress(0);
        setUploadSuccess(false);
        onUploadError?.(error.response?.data?.detail || "Upload failed");
      }
    },
    [onUploadSuccess, onUploadError] // Removed autoProcess and processingOption dependencies
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "video/*": [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    },
    multiple: false,
    disabled: uploading,
  });
  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          isDragActive
            ? "border-primary-400 bg-primary-50"
            : uploading
            ? "border-gray-300 bg-gray-50"
            : "border-gray-300 hover:border-primary-400 hover:bg-primary-50"
        } ${uploading ? "cursor-not-allowed" : "cursor-pointer"}`}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <div className="space-y-4">
            {uploadSuccess ? (
              <CheckCircleIcon className="mx-auto h-12 w-12 text-green-500" />
            ) : (
              <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            )}
            <div className="space-y-2">
              <p className="text-lg font-medium text-gray-900">
                {uploadSuccess ? "Upload Complete!" : "Uploading..."}
              </p>{" "}
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`bg-primary-600 h-2 rounded-full transition-all duration-300 ${
                    uploadProgress === 0
                      ? "w-0"
                      : uploadProgress <= 10
                      ? "w-1/12"
                      : uploadProgress <= 20
                      ? "w-1/6"
                      : uploadProgress <= 30
                      ? "w-1/4"
                      : uploadProgress <= 40
                      ? "w-1/3"
                      : uploadProgress <= 50
                      ? "w-1/2"
                      : uploadProgress <= 60
                      ? "w-3/5"
                      : uploadProgress <= 70
                      ? "w-2/3"
                      : uploadProgress <= 80
                      ? "w-4/5"
                      : uploadProgress <= 90
                      ? "w-11/12"
                      : "w-full"
                  }`}
                />
              </div>
              <p className="text-sm text-gray-500">{uploadProgress}%</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            <div>
              {" "}
              <p className="text-lg font-medium text-gray-900">
                {isDragActive
                  ? "Drop surveillance video here"
                  : "Upload surveillance video"}
              </p>{" "}
              <p className="text-sm text-gray-500 mt-1">
                Drag and drop your surveillance video file here, or click to
                select
              </p>
              <p className="text-xs text-gray-400 mt-2">
                Supports: MP4, AVI, MOV, WMV, FLV, WebM (max 100MB)
              </p>
              <p className="text-xs text-blue-600 mt-1">
                ✓ Videos will be automatically analyzed for anomaly detection
                using AI
              </p>
            </div>
            <button
              type="button"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              Select Video File
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoUpload;
