#[test]
fn composition_root_retains_coactivation_startup_order_not_the_loop() {
    let main = include_str!("../src/main.rs");
    let module = include_str!("../src/coactivation_tick.rs");

    let start = main
        .find("let coactivation_tick =")
        .expect("main.rs must retain explicit coactivation supervisor startup");
    let next_supervisor = main[start..]
        .find("// C3 — daemon self-check tick")
        .map(|offset| start + offset)
        .expect("main.rs must retain the next daemon supervisor boundary");
    let server = main[next_supervisor..]
        .find("serve(&socket, Router::new(hub)).await")
        .map(|offset| next_supervisor + offset)
        .expect("main.rs must retain final daemon server startup");
    let coactivation_wiring = &main[start..next_supervisor];

    assert!(start < next_supervisor && next_supervisor < server);
    assert!(coactivation_wiring.contains("CoactivationTickConfig::from_env()"));
    assert!(coactivation_wiring.contains("coactivation_tick::spawn(store, coactivation_tick)"));
    assert!(coactivation_wiring.contains("substrate-tick: disabled by env"));
    assert!(coactivation_wiring.contains("substrate-tick: no store configured, skipping"));
    assert!(!coactivation_wiring.contains("tokio::time::interval"));
    assert!(!coactivation_wiring.contains("decay_coactivation_once"));

    assert!(module.contains("tokio::time::interval(period)"));
    assert!(module.contains("MissedTickBehavior::Delay"));
    assert!(module.contains("interval.tick().await;"));
    assert!(module.contains("decay_coactivation_once(config.tau_secs, now, MAX_ITERATIONS)"));
}
