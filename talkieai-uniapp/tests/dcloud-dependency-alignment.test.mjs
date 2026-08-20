import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(testDir, "..");

function readJson(relativePath) {
  return JSON.parse(readFileSync(path.resolve(projectDir, relativePath), "utf8"));
}

test("keeps the HBuilder compiler packages on one DCloud release", () => {
  const packageJson = readJson("package.json");
  const declaredPackages = {
    ...packageJson.dependencies,
    ...packageJson.devDependencies,
  };
  const compilerVersions = Object.entries(declaredPackages)
    .filter(([name]) => name.startsWith("@dcloudio/") && name !== "@dcloudio/types")
    .map(([, version]) => version);

  assert.equal(new Set(compilerVersions).size, 1);

  const uniAppPackage = readJson("node_modules/@dcloudio/uni-app/package.json");
  const uniSharedPackage = readJson("node_modules/@dcloudio/uni-shared/package.json");
  const installedTypesPackage = readJson("node_modules/@dcloudio/types/package.json");

  assert.equal(uniSharedPackage.version, uniAppPackage.version);
  assert.equal(
    installedTypesPackage.version,
    uniAppPackage.peerDependencies["@dcloudio/types"]
  );
});
