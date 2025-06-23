import React from "react";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = "md",
  className = "",
}) => {
  const sizeClasses = {
    sm: "h-4 w-4",
    md: "h-8 w-8",
    lg: "h-12 w-12",
  };

  return (
    <div className={`${sizeClasses[size]} ${className} relative`}>
      {/* Outer surveillance camera ring */}
      <div className="absolute inset-0 border-2 border-blue-600 rounded-full animate-spin border-t-transparent" />

      {/* Inner security dot */}
      <div className="absolute inset-2 bg-blue-600 rounded-full animate-pulse" />

      {/* Center recording indicator */}
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-red-500 rounded-full animate-ping" />
    </div>
  );
};

export default LoadingSpinner;
