/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'error',
      from: {},
      to: { circular: true },
    },
    {
      name: 'not-to-unresolvable',
      severity: 'error',
      from: {},
      to: { couldNotResolve: true },
    },
    {
      name: 'no-test-imports-in-production',
      severity: 'error',
      from: {
        pathNot: ['^src/test/', '\\.test\\.(ts|tsx)$', '\\.spec\\.(ts|tsx)$'],
      },
      to: {
        path: '(^|/)src/test/|\\.(test|spec)\\.(ts|tsx)$',
      },
    },
    {
      name: 'no-app-imports-from-lower-layers',
      severity: 'error',
      from: { path: '^src/(features|domains|shared)/' },
      to: { path: '^src/app/' },
    },
    {
      name: 'no-feature-imports-from-domain-or-shared',
      severity: 'error',
      from: { path: '^src/(domains|shared)/' },
      to: { path: '^src/features/' },
    },
    {
      name: 'no-domain-imports-from-shared',
      severity: 'error',
      from: { path: '^src/shared/' },
      to: { path: '^src/domains/' },
    },
    {
      name: 'no-orphans',
      severity: 'warn',
      from: {
        orphan: true,
        pathNot: [
          '(^|/)\\.[^/]+',
          '\\.d\\.ts$',
          '(^|/)src/main\\.tsx$',
          '(^|/)src/test/setup\\.ts$',
          '(^|/)src/shared/lib/cn\\.ts$',
          '\\.test\\.(ts|tsx)$',
          '\\.spec\\.(ts|tsx)$',
        ],
      },
      to: {},
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    exclude: {
      path: ['node_modules', 'dist', 'coverage', '\\.vite'],
    },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: 'tsconfig.app.json' },
    enhancedResolveOptions: {
      exportsFields: ['exports'],
      conditionNames: ['import', 'require', 'node', 'default', 'types'],
      mainFields: ['module', 'main', 'types', 'typings'],
      extensions: ['.ts', '.tsx', '.js', '.jsx', '.json', '.css'],
    },
  },
};
