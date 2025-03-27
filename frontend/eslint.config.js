import antfu from '@antfu/eslint-config';

export default antfu({
  typescript: true, // Enable TypeScript support
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
});
