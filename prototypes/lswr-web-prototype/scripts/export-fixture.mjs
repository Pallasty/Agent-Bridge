import { chromium } from "playwright-core";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const url = process.env.LSWR_WEB_PROTO_URL ?? "http://127.0.0.1:5198/";
const executablePath =
  process.env.CHROME_EXECUTABLE_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const scriptDir = dirname(fileURLToPath(import.meta.url));
const prototypeRoot = resolve(scriptDir, "..");
const repoRoot = resolve(prototypeRoot, "../..");
const contractPath = resolve(
  process.env.LSWR_WEB_PROTO_CONTRACT ?? resolve(prototypeRoot, "contract/p8_world_core_contract.json")
);
const out = resolve(
  process.env.LSWR_WEB_PROTO_FIXTURE_OUT ?? resolve(repoRoot, "crates/world-core/tests/fixtures/p8_world_export.json")
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function exportWorld(page) {
  return page.evaluate(() => window.lswr.world_export());
}

async function loadContract() {
  return JSON.parse(await readFile(contractPath, "utf8"));
}

function latestVerification(packet) {
  return packet.verification.at(-1);
}

function countEvent(packet, eventType) {
  return packet.events.filter((event) => event.event_type === eventType).length;
}

function countVerdict(packet, verdict) {
  return packet.verification.filter((record) => record.verdict === verdict).length;
}

function normalizePacketForContract(packet, contract) {
  packet.events.forEach((event, index) => {
    event.at = `2026-06-06T00:00:${String(index + 1).padStart(2, "0")}.000Z`;
  });
  packet.contract = contract;
  return packet;
}

function assertContract(packet, contract) {
  const expected = contract.expectations;
  assert(packet.contract?.contract_id === contract.contract_id, "fixture contract_id is not attached");
  assert(packet.world.world_id === expected.world_id, "fixture world_id does not match contract");
  assert(packet.world.branch_id === expected.branch_id, "fixture branch_id does not match contract");
  assert(packet.projection.adapter === expected.projection_adapter, "fixture adapter does not match contract");
  assert(packet.events.length === expected.event_count, "fixture event count does not match contract");
  assert(
    packet.verification.length === expected.verification_count,
    "fixture verification count does not match contract"
  );
  assert(
    packet.rollback.available_groups.length === expected.rollback_group_count,
    "fixture rollback group count does not match contract"
  );
  expected.required_event_types.forEach((eventType) => {
    assert(countEvent(packet, eventType) > 0, `fixture missing required event type ${eventType}`);
  });
  expected.required_verdicts.forEach((verdict) => {
    assert(countVerdict(packet, verdict) > 0, `fixture missing required verdict ${verdict}`);
  });
  const notVerified = packet.verification.find((record) => record.verdict === "not_verified");
  assert(notVerified?.reason === contract.truth_boundary.not_verified_reason, "not_verified reason drifted");
  assert(
    notVerified?.verified_to === contract.truth_boundary.not_verified_source_verified_to,
    "not_verified source verified_to drifted"
  );
  const blocked = packet.verification.find((record) => record.verdict === "blocked");
  assert(blocked?.reason === contract.truth_boundary.blocked_reason, "blocked reason drifted");
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--use-angle=swiftshader", "--disable-gpu-sandbox"]
});

try {
  const contract = await loadContract();
  const page = await browser.newPage({ viewport: { width: 1360, height: 860 } });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForFunction(() => Boolean(window.lswr?.world_export));

  await page.getByRole("button", { name: "Add Cube" }).click();
  await page.getByRole("button", { name: "Move Cube" }).click();

  let packet = await exportWorld(page);
  const beforeSelect = countEvent(packet, "human.select");
  const point = await page.evaluate(() => window.lswr_debug.screen_for_entity("cube_01"));
  assert(point, "projection did not expose a screen point for cube_01");
  await page.mouse.click(point.clientX, point.clientY);
  packet = await exportWorld(page);
  assert(countEvent(packet, "human.select") > beforeSelect, "canvas click did not emit human.select");

  const beforeRejectVerification = latestVerification(packet);
  await page.getByRole("button", { name: "Reject" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).action_id === beforeRejectVerification.action_id, "reject rewrote verification");

  await page.getByRole("button", { name: "Force Miss" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).verdict === "not_verified", "forced miss did not produce not_verified");

  await page.getByRole("button", { name: "Blocked Move" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).verdict === "blocked", "blocked move did not produce blocked");

  await page.getByRole("button", { name: "Rollback" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).method === "web_scene_rollback_check", "rollback was not verified");

  packet = normalizePacketForContract(packet, contract);
  assertContract(packet, contract);

  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, `${JSON.stringify(packet, null, 2)}\n`);
  console.log(
    JSON.stringify(
      {
        contract: contract.contract_id,
        contractPath,
        out,
        events: packet.events.length,
        verification: packet.verification.length
      },
      null,
      2
    )
  );
} finally {
  await browser.close();
}
