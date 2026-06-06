import { chromium } from "playwright-core";
import { PNG } from "pngjs";

const url = process.env.LSWR_WEB_PROTO_URL ?? "http://127.0.0.1:5198/";
const executablePath =
  process.env.CHROME_EXECUTABLE_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function exportWorld(page) {
  return page.evaluate(() => window.lswr.world_export());
}

async function checkCanvas(page, label) {
  const scene = page.locator("#scene");
  const signal = readCanvasSignal(await scene.screenshot());
  assert(signal.width > 300 && signal.height > 300, `${label} canvas area is too small`);
  assert(signal.brightPixels > 1000, `${label} canvas screenshot appears blank`);
  assert(signal.colorBuckets > 12, `${label} canvas screenshot lacks visual variation`);
  return signal;
}

function latestVerification(packet) {
  return packet.verification.at(-1);
}

function countEvent(packet, eventType) {
  return packet.events.filter((event) => event.event_type === eventType).length;
}

function readCanvasSignal(buffer) {
  const png = PNG.sync.read(buffer);
  let brightPixels = 0;
  const colors = new Set();
  for (let index = 0; index < png.data.length; index += 16) {
    const r = png.data[index];
    const g = png.data[index + 1];
    const b = png.data[index + 2];
    if (r + g + b > 70) {
      brightPixels += 1;
    }
    colors.add(`${r >> 4}:${g >> 4}:${b >> 4}`);
  }
  return { brightPixels, colorBuckets: colors.size, width: png.width, height: png.height };
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

  const desktopCanvas = await checkCanvas(page, "desktop");

  let packet = await exportWorld(page);
  assert(packet.projection.projected_entities.some((entity) => entity.entity_id === "cube_01"), "initial cube_01 is not projected");

  await page.getByRole("button", { name: "Add Cube" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).verdict === "verified", "add_entity did not verify");
  assert(packet.projection.projected_entities.length >= 3, "added entity is missing projection evidence");

  await page.getByRole("button", { name: "Move Cube" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).verdict === "verified", "move_entity did not verify");
  assert(latestVerification(packet).evidence.position.length === 3, "move_entity evidence lacks position");

  const beforeSelect = countEvent(packet, "human.select");
  const point = await page.evaluate(() => window.lswr_debug.screen_for_entity("cube_01"));
  assert(point, "projection did not expose a screen point for cube_01");
  await page.mouse.click(point.clientX, point.clientY);
  packet = await exportWorld(page);
  assert(countEvent(packet, "human.select") > beforeSelect, "canvas click did not emit human.select");

  const beforeRejectVerification = latestVerification(packet);
  await page.getByRole("button", { name: "Reject" }).click();
  packet = await exportWorld(page);
  assert(countEvent(packet, "human.reject") >= 1, "reject did not emit human.reject");
  assert(latestVerification(packet).action_id === beforeRejectVerification.action_id, "reject rewrote latest verification");

  await page.getByRole("button", { name: "Force Miss" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).verdict === "not_verified", "forced projection miss did not become not_verified");
  assert(latestVerification(packet).reason === "projection_object_absent", "forced projection miss reason was not preserved");
  assert(packet.projection.unprojected_entities.length >= 1, "forced projection miss lacks unprojected evidence");
  assert((await page.locator("#latest-verdict").textContent()) === "not_verified", "not_verified state is not visible");

  const beforeBlocked = JSON.stringify(packet.entities.find((entity) => entity.entity_id === "platform").transform);
  await page.getByRole("button", { name: "Blocked Move" }).click();
  packet = await exportWorld(page);
  assert(latestVerification(packet).verdict === "blocked", "blocked action did not produce blocked verdict");
  assert(latestVerification(packet).reason === "locked_entity", "blocked action reason was not locked_entity");
  const afterBlocked = JSON.stringify(packet.entities.find((entity) => entity.entity_id === "platform").transform);
  assert(beforeBlocked === afterBlocked, "blocked action mutated semantic state");

  const beforeRollbackEvents = countEvent(packet, "runtime.rollback_applied");
  await page.getByRole("button", { name: "Rollback" }).click();
  packet = await exportWorld(page);
  assert(countEvent(packet, "runtime.rollback_applied") > beforeRollbackEvents, "rollback did not emit runtime.rollback_applied");
  assert(latestVerification(packet).method === "web_scene_rollback_check", "rollback did not produce rollback verification");

  assert(packet.world.world_id === "lswr_web_proto_01", "readback lacks world identity");
  assert(Array.isArray(packet.events) && Array.isArray(packet.verification), "readback lacks event/evidence arrays");
  assert(packet.projection.adapter === "threejs_web", "readback lacks projection adapter");

  const mobile = await browser.newPage({ viewport: { width: 390, height: 780 }, isMobile: true });
  await mobile.goto(url, { waitUntil: "networkidle" });
  await mobile.waitForFunction(() => Boolean(window.lswr?.world_export));
  const mobileCanvas = await checkCanvas(mobile, "mobile");
  const mobileLayout = await mobile.evaluate(() => ({
    viewportWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    sceneHeight: Math.round(document.querySelector("#scene").getBoundingClientRect().height)
  }));
  assert(mobileLayout.scrollWidth <= mobileLayout.viewportWidth + 1, "mobile layout has horizontal overflow");
  assert(mobileLayout.sceneHeight >= 400, "mobile scene pane is too short");
  await mobile.close();

  const result = {
    url,
    canvasSignal: {
      desktop: desktopCanvas,
      mobile: mobileCanvas
    },
    mobileLayout,
    gates: {
      "WEB-001": "passed",
      "WEB-002": "passed",
      "WEB-003": "passed",
      "WEB-004": "passed",
      "WEB-005": "passed",
      "WEB-006": "passed",
      "WEB-007": "passed",
      "WEB-008": "passed"
    },
    events: packet.events.length,
    verification: packet.verification.length,
    latest: latestVerification(packet)
  };
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
