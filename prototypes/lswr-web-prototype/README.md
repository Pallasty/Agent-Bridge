# LSWR Web Prototype

Disposable P8 prototype for the Live Semantic World Runtime mainline.

Run:

```sh
npm install
npm run dev -- --port 5198
npm run verify:browser
```

Scope:

- semantic scene JSON is the source of truth;
- Three.js is only the projection adapter;
- human click/drag/accept/reject produce structured events;
- agent readback uses `window.lswr.world_export()`;
- `not_verified` remains visibly unconfirmed;
- rollback is action-log based;
- no Agent-Bridge MCP tool registration, no Step D resume, no #92/#94 wiring.
