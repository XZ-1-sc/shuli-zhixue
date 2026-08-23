module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  extends: ["eslint:recommended", "plugin:vue/vue3-essential", "prettier"],
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  rules: {
    "no-unused-vars": ["warn", { argsIgnorePattern: "^_", caughtErrors: "none" }],
    "vue/multi-word-component-names": "off",
    "vue/no-unused-components": "warn"
  }
};
