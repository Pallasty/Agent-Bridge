// wit-bindgen's generated ABI shims contain the required unsafe export glue;
// the handwritten transformation below does not use unsafe operations.
#![allow(unsafe_code)]

wit_bindgen::generate!({
    path: "../world.wit",
});

struct BusinessProbe;

impl Guest for BusinessProbe {
    fn evaluate(input: WorldStateInput) -> WorldStateReport {
        let occupancy_per_mille = input
            .occupied_cells
            .checked_mul(1000)
            .and_then(|value| value.checked_div(input.entity_count.max(1)))
            .unwrap_or(0);
        WorldStateReport {
            revision: input.revision,
            entity_count: input.entity_count,
            occupied_cells: input.occupied_cells,
            transition_count: input.transition_count,
            occupancy_per_mille,
            report_code: "WORLD_STATE_V0".to_string(),
        }
    }
}

export!(BusinessProbe);
