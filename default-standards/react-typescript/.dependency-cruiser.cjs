module.exports = {
  forbidden: [
    {
      name: 'domain-isolation',
      severity: 'error',
      comment: 'Domain code cannot depend on UI or application code.',
      from: { path: '^src/domain/' },
      to: { path: '^src/(ui|app)/' },
    },
  ],
  options: {
    includeOnly: '^src/',
    tsConfig: { fileName: 'tsconfig.json' },
  },
};
