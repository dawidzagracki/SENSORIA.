import coreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const eslintConfig = [
  {
    ignores: [
      ".next/**",
      ".next-audit/**",
      "node_modules/**",
      "out/**",
      "build/**",
      "test-results/**",
      "playwright-report/**",
      "next-env.d.ts",
    ],
  },
  ...coreWebVitals,
  ...nextTypescript,
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off",
      // New in eslint-plugin-react-hooks 7 (Next 16). Our effects deliberately hydrate state from
      // cookies, URL and storage after mount; rewriting 30+ working components is out of scope.
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default eslintConfig;
