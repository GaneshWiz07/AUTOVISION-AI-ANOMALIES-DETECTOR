// Module declaration file to help with TypeScript compilation

// Wildcard module declarations to catch all relative imports
declare module '../*' {
  const content: any;
  export = content;
  export * from '*';
}

declare module './*' {
  const content: any;
  export = content;
  export * from '*';
}

declare module '*.tsx' {
  const component: React.ComponentType<any>;
  export default component;
}

declare module '*.ts' {
  const content: any;
  export default content;
}

// Specific declaration for the API module
declare module '../lib/api' {
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

  export const authAPI: any;
  export const videoAPI: any;
  export const eventAPI: any;
  export const systemAPI: any;
  export const settingsAPI: any;
  export const cleanupAPI: any;
  
  const api: any;
  export default api;
}

// General pattern for lib modules
declare module '../lib/*' {
  const content: any;
  export = content;
}

declare module './lib/*' {
  const content: any;
  export = content;
}

declare module '*/lib/api' {
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

  export const authAPI: any;
  export const videoAPI: any;
  export const eventAPI: any;
  export const systemAPI: any;
  export const settingsAPI: any;
  export const cleanupAPI: any;
  
  const api: any;
  export default api;
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

// Basic React types if not available
declare namespace React {
  interface ComponentType<P = {}> {
    (props: P): JSX.Element | null;
  }
  
  interface FC<P = {}> extends ComponentType<P> {}
  
  interface ReactNode {
    [key: string]: any;
  }
}

declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
  
  interface Element extends React.ReactNode {}
}
