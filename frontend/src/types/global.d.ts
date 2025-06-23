// Module declaration file to help with TypeScript compilation

// Specific declaration for the API module with path mapping
declare module '@/lib/api' {
  export interface AuthUser {
    id: string;
    email: string;
    full_name?: string;
    avatar_url?: string;
  }

  export interface Video {
    id: string;
    filename: string;
    original_name: string;
    file_path: string;
    file_url?: string;
    file_size: number;
    duration_seconds?: number;
    fps?: number;
    resolution?: string;
    upload_status: string;
    storage_provider?: string;
    created_at: string;
    updated_at: string;
  }

  export interface Event {
    id: string;
    video_id: string;
    event_type: string;
    anomaly_score: number;
    confidence: number;
    timestamp_seconds: number;
    frame_number: number;
    description?: string;
    is_alert: boolean;
    is_false_positive?: boolean;
    created_at: string;
  }

  export interface UserSettings {
    anomaly_threshold: number;
    frame_sampling_rate: number;
    auto_delete_old_videos: boolean;
    video_retention_days: number;
  }

  export interface VideoAnalysis {
    video_id: string;
    video_info: any;
    analysis_summary: any;
    events: Event[];
    rl_metrics: any;
    rag_stats: any;
  }

  export interface SettingsUpdateRequest {
    anomaly_threshold?: number;
    frame_sampling_rate?: number;
    auto_delete_old_videos?: boolean;
    video_retention_days?: number;
  }

  export const authAPI: {
    login: (email: string, password: string) => Promise<any>;
    signup: (email: string, password: string, full_name?: string) => Promise<any>;
    logout: () => Promise<void>;
    getCurrentUser: () => Promise<AuthUser>;
    refreshToken: (refreshToken: string) => Promise<any>;
  };

  export const videoAPI: {
    uploadVideo: (file: File) => Promise<any>;
    getVideos: (limit?: number) => Promise<{ videos: Video[] }>;
    getVideo: (videoId: string) => Promise<Video>;
    getVideoAnalysis: (videoId: string) => Promise<VideoAnalysis>;
    deleteVideo: (videoId: string) => Promise<any>;
    getVideoEvents: (videoId: string) => Promise<{ events: Event[] }>;
    processVideo: (videoId: string) => Promise<any>;
  };

  export const eventAPI: {
    getEvents: (limit?: number) => Promise<{ events: Event[] }>;
    updateEvent: (eventId: string, data: any) => Promise<any>;
    provideFeedback: (eventId: string, isFalsePositive: boolean, feedbackScore: number) => Promise<any>;
  };

  export const systemAPI: {
    getStatus: () => Promise<any>;
    getMetrics: () => Promise<any>;
    getSystemEvents: (limit?: number, eventType?: string) => Promise<any>;
    getRLStatus: () => Promise<any>;
    resetRLTraining: () => Promise<any>;
    getRAGPatterns: (patternType?: string) => Promise<any>;
    getRAGStats: () => Promise<any>;
  };

  export const settingsAPI: {
    getSettings: () => Promise<UserSettings>;
    updateSettings: (settings: SettingsUpdateRequest) => Promise<UserSettings>;
  };

  export const cleanupAPI: {
    getCleanupPreview: () => Promise<any>;
    runCleanup: () => Promise<any>;
  };
  
  const api: any;
  export default api;
}

// Also declare for relative paths
declare module '../lib/api' {
  export * from '@/lib/api';
}

declare module './lib/api' {
  export * from '@/lib/api';
}

// Component module declarations
declare module '*.tsx' {
  const component: React.ComponentType<any>;
  export default component;
}

declare module '*.ts' {
  const content: any;
  export default content;
}

// Fallback for other lib modules (but not api)
declare module '../lib/supabase' {
  const content: any;
  export default content;
}

// General wildcard fallback (but with lower priority)
declare module '../*' {
  const content: any;
  export default content;
}

declare module './*' {
  const content: any;
  export default content;
}

// Extend the import.meta.env interface to include DEV and other Vite properties
declare interface ImportMetaEnv {
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly MODE: string;
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
  readonly VITE_SUPABASE_URL: string;
  readonly VITE_SUPABASE_ANON_KEY: string;
}

declare interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// React module declarations
declare module 'react' {
  export * from 'react';
  export = React;
  export as namespace React;
  namespace React {
    interface ComponentType<P = {}> {
      (props: P): JSX.Element | null;
    }
    interface FC<P = {}> extends ComponentType<P> {}
    type ReactNode = any;
    function useState<T>(initialState: T | (() => T)): [T, (value: T | ((prev: T) => T)) => void];
    function useEffect(effect: () => void | (() => void), deps?: any[]): void;
    function useContext<T>(context: any): T;
    function useCallback<T extends (...args: any[]) => any>(callback: T, deps: any[]): T;
    function createContext<T>(defaultValue: T): any;
    const Fragment: any;
    const StrictMode: any;
  }
}

declare module 'react-dom/client' {
  export function createRoot(container: Element): {
    render: (element: any) => void;
  };
}

declare module 'react-router-dom' {
  export const BrowserRouter: any;
  export const Routes: any;
  export const Route: any;
  export const Link: any;
  export const Navigate: any;
  export function useNavigate(): any;
  export function useParams(): any;
  export function useSearchParams(): any;
}

declare module '@heroicons/react/24/outline' {
  export const PlayIcon: any;
  export const EyeIcon: any;
  export const TrashIcon: any;
  export const VideoCameraIcon: any;
  export const ExclamationTriangleIcon: any;
  export const ChartBarIcon: any;
  export const CogIcon: any;
  export const ArrowPathIcon: any;
  export const CheckCircleIcon: any;
  export const XCircleIcon: any;
  export const InformationCircleIcon: any;
  export const CloudArrowUpIcon: any;
}

declare module 'react-dropzone' {
  export function useDropzone(options: any): any;
}

declare module 'react/jsx-runtime' {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
}
