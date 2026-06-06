import { chromium } from "playwright-core";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const url = process.env.LSWR_WEB_PROTO_URL ?? "http://127.0.0.1:5198/";
const executablePath =
  process.env.CHROME_EXECUTABLE_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const out = resolve(
  process.env.LSWR_WEB_PROTO_FIXTURE_OUT ?? "../../crates/world-core/tests/fixtures/p8_world_export.json"
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function exportWorld(page) {
  return page.evaluate(() => window.lswr.world_export());
}

function latestVerification(packet) {
  return packet.verification.at(-1);
}

function countEvent(packet, eventType) {
  return packet.events.filter((event) => event.event_type === eventType).length;
}

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--use-angle=swiftshader", "--disable-gpu-sandbox"]
});

try {
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

  packet.events.forEach((event, index) => {
    event.at = `2026-06-06T00:00:${String(index + 1).padStart(2, "0")}.000Z`;
  });

  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, `${JSON.stringify(packet, null, 2)}\n`);
  console.log(JSON.stringify({ out, events: packet.events.length, verification: packet.verification.length }, null, 2));
} finally {
  await browser.close();
}
