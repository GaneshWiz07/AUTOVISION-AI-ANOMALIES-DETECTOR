/// <reference types="vite/client" />

declare module "*.tsx" {
  const content: React.ComponentType<any>;
  export default content;
}

declare module "*.ts" {
  const content: any;
  export default content;
}

// Ensure global types are available
declare global {
  namespace JSX {
    interface Element extends React.ReactElement<any, any> {}
  }
}

export {};
