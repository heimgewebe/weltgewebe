import js from "@eslint/js";
import globals from "globals";
import svelte from "eslint-plugin-svelte";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

const IGNORE = [
  ".svelte-kit/",
  "build/",
  "dist/",
  "node_modules/",
  "public/demo.png",
  "scripts/record-screenshot.mjs",
];

export default [
  {
    ignores: IGNORE,
  },
  ...svelte.configs["flat/recommended"],
  {
    files: ["**/*.svelte"],
    languageOptions: {
      parserOptions: {
        parser: tsParser,
      },
    },
    rules: {
      "svelte/no-at-html-tags": "error",
    },
  },
  {
    files: ["playwright.config.ts", "scripts/**/*.js"],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
  {
    files: ["**/*.ts", "**/*.js"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2023,
        sourceType: "module",
      },
      globals: globals.browser,
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs["recommended"].rules,
      "no-undef": "off", // TypeScript handles this
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
];
