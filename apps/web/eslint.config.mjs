// Flat config (ESLint 9). Next 16 removed `next lint`; eslint-config-next 16
// ships flat-config arrays, so the lint script runs the ESLint CLI directly.
// Note: eslint 10 is blocked by eslint-plugin-react (peer <=9.x, removed-API
// crash) — re-try when eslint-config-next upgrades its plugin set.
import coreWebVitals from "eslint-config-next/core-web-vitals";

const config = [
  {
    ignores: [".next/**", "node_modules/**", "test-results/**", "next-env.d.ts"],
  },
  ...coreWebVitals,
  {
    rules: {
      // The strict set-state-in-effect rule arrived with eslint-config-next 16
      // and flags the app's pre-existing fetch-on-mount patterns (8 sites).
      // Kept visible as warnings pending a dedicated data-loading refactor.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default config;
