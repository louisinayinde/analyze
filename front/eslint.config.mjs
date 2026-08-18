import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Désactive les règles ESLint stylistiques qui entreraient en conflit avec Prettier.
  prettier,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Généré depuis le contrat OpenAPI backend (H2, backlog.md) — pas de
    // lint stylistique sur du code produit par une machine.
    "shared/api/schema.gen.ts",
  ]),
]);

export default eslintConfig;
