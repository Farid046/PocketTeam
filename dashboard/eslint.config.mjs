import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import globals from "globals";

export default tseslint.config(
  // Base JS recommended rules
  js.configs.recommended,

  // TypeScript recommended rules (with type-aware parser)
  ...tseslint.configs.recommended,

  // React plugin flat config (recommended)
  {
    ...reactPlugin.configs.flat.recommended,
    settings: {
      react: {
        version: "detect",
      },
    },
  },

  // React Hooks rules
  {
    plugins: {
      "react-hooks": reactHooksPlugin,
    },
    rules: {
      ...reactHooksPlugin.configs.recommended.rules,
      // Downgrade advanced React Compiler rules to warnings for existing code.
      // These are real quality issues but should not block CI on an existing codebase.
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/immutability": "warn",
    },
  },

  // TypeScript + React frontend source files
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.es2022,
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    rules: {
      // TypeScript handles no-undef — disable redundant JS rule
      "no-undef": "off",

      // TypeScript handles unused vars — disable JS version, warn via TS rule
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": "warn",

      // React 19 does not require React in scope for JSX
      "react/react-in-jsx-scope": "off",

      // TypeScript provides prop-type safety
      "react/prop-types": "off",

      // Reasonable quality rules
      "no-console": ["warn", { allow: ["warn", "error"] }],
      "no-debugger": "error",
      "prefer-const": "error",
      "no-var": "error",

      // TypeScript-specific: allow explicit any where needed
      "@typescript-eslint/no-explicit-any": "warn",

      // Allow non-null assertions (common in React code)
      "@typescript-eslint/no-non-null-assertion": "warn",
    },
  },

  // Server-side TypeScript files (Node globals)
  {
    files: ["src/server/**/*.ts"],
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.es2022,
      },
    },
  },

  // React Three Fiber / Three.js 3D components use custom JSX props
  // that the React plugin incorrectly flags as unknown HTML properties.
  {
    files: ["src/**/*3D*.{ts,tsx}", "src/**/office3d/**/*.{ts,tsx}"],
    rules: {
      "react/no-unknown-property": "off",
    },
  },

  // Ignore built output and generated files
  {
    ignores: ["dist/**", "node_modules/**", "*.config.{js,ts,mjs}"],
  },
);
