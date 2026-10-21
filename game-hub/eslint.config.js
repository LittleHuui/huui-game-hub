import js from '@eslint/js';
import vue from 'eslint-plugin-vue';
import promise from 'eslint-plugin-promise';
import jsdoc from 'eslint-plugin-jsdoc';

const browserGlobals = {
  AbortController: 'readonly',
  crypto: 'readonly',
  document: 'readonly',
  fetch: 'readonly',
  localStorage: 'readonly',
  location: 'readonly',
  navigator: 'readonly',
  sessionStorage: 'readonly',
  window: 'readonly'
};

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'public/**']
  },
  js.configs.recommended,
  ...vue.configs['flat/essential'],
  {
    files: ['src/**/*.{js,vue}', 'scripts/**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...browserGlobals,
        console: 'readonly',
        process: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        WebSocket: 'readonly',
        ResizeObserver: 'readonly',
        requestAnimationFrame: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly'
      }
    },
    plugins: { promise, jsdoc },
    rules: {
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'promise/always-return': 'off',
      'promise/catch-or-return': ['error', { allowThen: true }],
      'vue/no-mutating-props': 'error',
      'vue/no-unused-components': 'error',
      'vue/no-unused-vars': 'error'
    }
  },
  {
    files: ['scripts/**/*.mjs'],
    languageOptions: {
      globals: {
        Buffer: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly'
      }
    }
  },
  {
    files: [
      'src/services/strategyTurnGameViewService.js',
      'src/services/strategyTurnActionIntentService.js',
      'src/games/**/gameModule.js',
      'src/games/gameModuleRegistry.js'
    ],
    rules: {
      'jsdoc/require-jsdoc': [
        'error',
        {
          require: {
            FunctionDeclaration: true,
            MethodDefinition: true,
            ClassDeclaration: false,
            ArrowFunctionExpression: false,
            FunctionExpression: false
          }
        }
      ]
    }
  }
];
