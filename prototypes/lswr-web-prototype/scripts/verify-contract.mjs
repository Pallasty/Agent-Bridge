import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const prototypeRoot = resolve(scriptDir, "..");
const repoRoot = resolve(prototypeRoot, "../..");
const contractPath = resolve(
  process.env.LSWR_WEB_PROTO_CONTRACT ?? resolve(prototypeRoot, "contract/p8_world_core_contract.json")
);
const fixturePath = resolve(
  process.env.LSWR_WEB_PROTO_FIXTURE_OUT ?? resolve(repoRoot, "crates/world-core/tests/fixtures/p8_world_export.json")
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function countEvent(packet, eventType) {
  return packet.events.filter((event) => event.event_type === eventType).length;
}

function countVerdict(packet, verdict) {
  return packet.verification.filter((record) => record.verdict === verdict).length;
}

const contract = JSON.parse(await readFile(contractPath, "utf8"));
const packet = JSON.parse(await readFile(fixturePath, "utf8"));
const expected = contract.expectations;

assert(packet.contract?.schema === contract.schema, "fixture contract schema mismatch");
assert(packet.contract?.contract_id === contract.contract_id, "fixture contract id mismatch");
assert(packet.contract?.fixture_id === contract.fixture_id, "fixture id mismatch");
assert(packet.contract?.paths?.fixture === contract.paths.fixture, "fixture path metadata mismatch");
assert(packet.world.world_id === expected.world_id, "world_id mismatch");
assert(packet.world.branch_id === expected.branch_id, "branch_id mismatch");
assert(packet.projection.adapter === expected.projection_adapter, "projection adapter mismatch");
assert(packet.events.length === expected.event_count, "event count mismatch");
assert(packet.verification.length === expected.verification_count, "verification count mismatch");
assert(packet.rollback.available_groups.length === expected.rollback_group_count, "rollback group count mismatch");

expected.required_event_types.forEach((eventType) => {
  assert(countEvent(packet, eventType) > 0, `missing event type ${eventType}`);
});
expected.required_verdicts.forEach((verdict) => {
  assert(countVerdict(packet, verdict) > 0, `missing verdict ${verdict}`);
});

packet.events.forEach((event, index) => {
  const expectedAt = `2026-06-06T00:00:${String(index + 1).padStart(2, "0")}.000Z`;
  assert(event.at === expectedAt, `event ${event.event_id} timestamp is not deterministic`);
});

const notVerified = packet.verification.find((record) => record.verdict === "not_verified");
assert(notVerified, "missing not_verified record");
assert(
  notVerified.reason === contract.truth_boundary.not_verified_reason,
  "not_verified reason does not match contract"
);
assert(
  notVerified.verified_to === contract.truth_boundary.not_verified_source_verified_to,
  "not_verified source verified_to does not match contract"
);

const blocked = packet.verification.find((record) => record.verdict === "blocked");
assert(blocked, "missing blocked record");
assert(blocked.reason === contract.truth_boundary.blocked_reason, "blocked reason does not match contract");

console.log(
  JSON.stringify(
    {
      contract: contract.contract_id,
      fixture: fixturePath,
      events: packet.events.length,
      verification: packet.verification.length,
      rollbackGroups: packet.rollback.available_groups.length
    },
    null,
    2
  )
);
