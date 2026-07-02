// TypeScript 6 (TS2882) requires declarations for side-effect CSS imports
// (app/globals.css, @xyflow/react/dist/style.css). Next.js handles the actual
// CSS at build time; this only satisfies the type checker.
declare module "*.css";
