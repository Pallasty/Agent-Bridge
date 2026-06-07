# LSWR Web Prototype

Disposable P8 prototype for the Live Semantic World Runtime mainline.

Run:

```sh
npm install
npm run dev -- --port 5198
npm run verify:browser
npm run export:fixture
npm run verify:contract
```

Scope:

- semantic scene JSON is the source of truth;
- Three.js is only the projection adapter;
- human click/drag/accept/reject produce structured events;
- agent readback uses `window.lswr.world_export()`;
- `not_verified` remains visibly unconfirmed;
- rollback is action-log based;
- `contract/p8_world_core_contract.json` defines the stable export fixture
  contract consumed by `ab-world-core`;
- no Agent-Bridge MCP tool registration, no Step D resume, no #92/#94 wiring.
