import { defineConfig } from "tsup";

export default defineConfig({
  entry: [
    "src/index.ts",
    "src/fzfmatch/index.ts",
    "src/config/index.ts",
    "src/shortid/index.ts",
  ],
  format: ["esm"],
  dts: true,
  clean: true,
  target: "node22",
});
