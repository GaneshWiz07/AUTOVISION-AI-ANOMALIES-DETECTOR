// Module declaration file to help with TypeScript compilation
declare module '*.tsx' {
  const component: React.ComponentType<any>;
  export default component;
}

declare module '*.ts' {
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
