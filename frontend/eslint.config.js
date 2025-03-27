import antfu from '@antfu/eslint-config';

export default antfu(
  {
    typescript: {
      tsconfigPath: './tsconfig.json',
      enableTypeChecking: true,
    },
    react: true,
    rules: {
      '@stylistic/member-delimiter-style': [
        'error',
        {
          multiline: {
            delimiter: 'semi',
            requireLast: true,
          },
          singleline: {
            delimiter: 'semi',
            requireLast: true,
          },
          multilineDetection: 'brackets',
        },
      ],
      'style/semi': ['error', 'always'], // Enforce semicolons
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    rules: {
      'node/prefer-global/process': 'error',
      'ts/no-deprecated': 'error',
    },
  },
);
