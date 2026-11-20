// @ts-check
import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

/** Files that run in Node (build scripts, Electron main, tests, configs). */
const nodeFiles = [
  'scripts/**',
  'apps/desktop/scripts/**',
  'apps/desktop/electron/**',
  'apps/desktop/e2e/**',
  '**/*.config.{js,ts,mjs}',
  '**/vitest.setup.ts',
];

/** Files that run in a browser context. */
const browserFiles = [
  'apps/desktop/renderer/**',
  'apps/desktop/player/**',
  'packages/design-system/**',
  'packages/event-protocol/**',
];

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/out/**',
      '**/release/**',
      '**/coverage/**',
      '**/playwright-report/**',
      '**/test-results/**',
      'services/**',
      'packages/contracts/src/generated/**',
    ],
  },

  js.configs.recommended,

  // TypeScript: type-aware rules everywhere.
  {
    files: ['**/*.{ts,tsx}'],
    extends: [...tseslint.configs.recommendedTypeChecked, ...tseslint.configs.stylisticTypeChecked],
    languageOptions: {
      parserOptions: {
        project: [
          './tsconfig.json',
          './packages/*/tsconfig.json',
          './apps/desktop/tsconfig.json',
          './apps/desktop/tsconfig.node.json',
        ],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': [
        'error',
        { checksVoidReturn: { attributes: false } },
      ],
      '@typescript-eslint/consistent-type-definitions': ['error', 'interface'],
      // Interface-vs-type and Record-vs-index-signature are style preferences we leave open.
      '@typescript-eslint/consistent-indexed-object-style': 'off',
      // Explicit null guards keep type narrowing for the lines that follow.
      '@typescript-eslint/prefer-optional-chain': 'off',
      '@typescript-eslint/prefer-nullish-coalescing': [
        'error',
        { ignorePrimitives: { string: true, boolean: true } },
      ],
    },
  },

  // Plain JavaScript (build scripts): no type information available.
  {
    files: ['**/*.{js,mjs,cjs}'],
    extends: [tseslint.configs.disableTypeChecked],
  },

  { files: nodeFiles, languageOptions: { globals: { ...globals.node } } },
  { files: browserFiles, languageOptions: { globals: { ...globals.browser } } },

  // React: hook rules apply to every UI module (custom hooks live in .ts files);
  // accessibility rules apply to markup.
  {
    files: [
      'apps/desktop/renderer/**/*.{ts,tsx}',
      'apps/desktop/player/**/*.{ts,tsx}',
      'packages/design-system/**/*.{ts,tsx}',
    ],
    extends: [reactHooks.configs.flat.recommended],
  },
  { files: ['**/*.tsx'], extends: [jsxA11y.flatConfigs.recommended] },

  // The renderer and player must never reach for Node or Electron.
  {
    files: browserFiles,
    ignores: ['**/*.config.{js,ts}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: ['electron', 'fs', 'path', 'child_process', 'os', 'crypto'].map((name) => ({
            name,
            message:
              'Renderer and player code cannot use Node or Electron APIs. Go through window.adle.',
          })),
          patterns: [
            {
              group: ['node:*'],
              message:
                'Renderer and player code cannot use Node or Electron APIs. Go through window.adle.',
            },
            {
              // Only the shared IPC *types* may cross from the Electron side.
              group: ['**/electron/main/**', '**/electron/preload/**'],
              message: 'Main-process and preload code must not be imported into the renderer.',
            },
          ],
        },
      ],
      'no-restricted-globals': [
        'error',
        { name: 'localStorage', message: 'State lives in the core database, not web storage.' },
        { name: 'sessionStorage', message: 'State lives in the core database, not web storage.' },
        { name: 'fetch', message: 'The renderer has no network access. Use the core client.' },
      ],
    },
  },

  // Tests may be looser about unsafe access into fixtures.
  {
    files: ['**/*.test.{ts,tsx}', 'apps/desktop/e2e/**'],
    rules: {
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-argument': 'off',
      '@typescript-eslint/unbound-method': 'off',
      '@typescript-eslint/require-await': 'off',
      'no-restricted-globals': 'off',
      'no-restricted-imports': 'off',
    },
  },
);
