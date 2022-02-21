// npm install --save-dev @commitlint/config-conventional @commitlint/cli
// ./node_modules/.bin/commitlint --print-config

// commitlint 的默认格式为
// type(scope?): subject
// body?
// footer?

// 数组中第一位为level，可选0,1,2，0为disable，1为warning，2为error
// 第二位为应用与否，可选always|never
// 第三位该rule的值。

module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "body-leading-blank": [2, "always"],
    "body-max-line-length": [0],
    "header-max-length": [0],
    "subject-empty": [2, "never"],
    "subject-full-stop": [0, "never"],
    "type-case": [2, "always", "lower-case"],
    "subject-case": [0, "never"],
    "type-empty": [2, "never"],
    "type-enum": [
      2,
      "always",
      ["fix", "feat", "refactor", "docs", "chore", "style", "pref", "test"],
    ],
    "body-enum": [2, "always", ["Log:"]],
  },

  // plugins doc: https://github.com/conventional-changelog/commitlint/blob/32daec22/docs/reference-plugins.md

  plugins: [
    {
      rules: {
        "body-enum": (parsed, when, value) => {
          // 检查 body 是否有Log:
          if (!parsed.body) {
            return [false, `缺少描述信息`];
          }

          var result = false;

          for (let enumValue of value) {
            if (parsed.body.indexOf(enumValue) >= 0) {
              result = true;
            }
          }

          return [
            when == "always" ? result : true,
            `描述信息中缺少 [${value.join("/ ")}]`,
          ];
        },
      },
    },
  ],
  helpUrl:
    "https://wikidev.uniontech.com/Commit%E6%8F%90%E4%BA%A4%E8%A7%84%E8%8C%83",
};
