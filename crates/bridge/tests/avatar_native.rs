use ab_bridge::avatar_native::{
    alpha_bbox, animated_frame_coords, animation_frame_index, apply_native_sprite_plan,
    argb8888_le, decode_sidecar_sprite_asset, native_prompt_observed_opacity,
    native_prompt_opacity, native_prompt_plan, native_sprite_asset_for_mode,
    native_sprite_plan_from_state_value, native_state_http_request_parts,
    native_transparent_plan_json, paint_native_prompt_bubble, paint_rgba_sprite_centered,
    paint_transparent_probe_frame, parse_native_anchor, parse_native_layer,
    sidecar_asset_id_from_route, sprite_cell, NativeAnchor, NativeLayer, NativePromptPlan,
    NativeTransparentOptions, RgbaSprite, DEFAULT_NATIVE_FRAME_COUNT,
    DEFAULT_NATIVE_FRAME_INTERVAL_MS, DEFAULT_NATIVE_SPRITE_CELL_HEIGHT,
    DEFAULT_NATIVE_SPRITE_CELL_WIDTH, DEFAULT_NATIVE_TRANSPARENT_TITLE, NATIVE_PROMPT_SCHEMA,
};
use serde_json::json;
use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn native_prompt_state_is_bounded_and_expires() {
    let dir = tempfile::tempdir().expect("tempdir");
    let path = dir.path().join("prompt.json");
    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("wall clock")
        .as_millis() as u64;
    fs::write(
        &path,
        serde_json::to_vec(&json!({
            "schema": NATIVE_PROMPT_SCHEMA,
            "text": "需要我过去吗？",
            "expires_at_unix_ms": now_ms + 60_000,
        }))
        .expect("serialize prompt"),
    )
    .expect("write prompt");
    let prompt = native_prompt_plan(&path)
        .expect("parse prompt")
        .expect("unexpired prompt");
    assert_eq!(prompt.text, "需要我过去吗？");

    fs::write(
        &path,
        serde_json::to_vec(&json!({
            "schema": NATIVE_PROMPT_SCHEMA,
            "text": "需要我过去吗？",
            "expires_at_unix_ms": now_ms.saturating_sub(1),
        }))
        .expect("serialize expired prompt"),
    )
    .expect("write expired prompt");
    assert!(native_prompt_plan(&path)
        .expect("parse expired prompt")
        .is_none());
}

#[test]
fn native_prompt_opacity_has_bounded_fade_in_hold_and_fade_out() {
    let prompt = NativePromptPlan {
        text: "需要我过去吗？".to_string(),
        created_at_unix_ms: 1_000,
        expires_at_unix_ms: 3_000,
    };
    assert_eq!(native_prompt_opacity(&prompt, 999), 0);
    assert_eq!(native_prompt_opacity(&prompt, 1_000), 0);
    assert!(native_prompt_opacity(&prompt, 1_160) > 120);
    assert_eq!(native_prompt_opacity(&prompt, 1_320), 255);
    assert_eq!(native_prompt_opacity(&prompt, 2_000), 255);
    assert!(native_prompt_opacity(&prompt, 2_840) > 120);
    assert_eq!(native_prompt_opacity(&prompt, 3_000), 0);
}

#[test]
fn observed_prompt_fade_in_survives_state_poll_delay() {
    let prompt = NativePromptPlan {
        text: "需要我过去吗？".to_string(),
        created_at_unix_ms: 1_000,
        expires_at_unix_ms: 4_000,
    };
    // The renderer first observes this prompt 700ms after publication. Fade-in
    // must still start at zero instead of appearing fully opaque immediately.
    assert_eq!(native_prompt_observed_opacity(&prompt, 0, 1_700), 0);
    assert!(native_prompt_observed_opacity(&prompt, 80, 1_780) > 50);
    assert!(native_prompt_observed_opacity(&prompt, 160, 1_860) > 120);
    assert_eq!(native_prompt_observed_opacity(&prompt, 320, 2_020), 255);
    assert_eq!(native_prompt_observed_opacity(&prompt, 800, 3_680), 255);
    assert!(native_prompt_observed_opacity(&prompt, 900, 3_840) > 120);
    assert_eq!(native_prompt_observed_opacity(&prompt, 1_000, 4_000), 0);
}

#[test]
fn native_prompt_bubble_paints_visible_chinese_glyphs_when_noto_is_available() {
    let path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc";
    if !std::path::Path::new(path).is_file() {
        return;
    }
    let font = fontdue::Font::from_bytes(
        fs::read(path).expect("read Noto CJK"),
        fontdue::FontSettings::default(),
    )
    .expect("decode Noto CJK collection");
    let mut canvas = vec![0_u8; 90 * 130 * 4];
    paint_native_prompt_bubble(&mut canvas, 90, 130, "需要我过去吗？", &font, 255);
    let opaque = canvas.chunks_exact(4).filter(|pixel| pixel[3] > 0).count();
    let dark_glyph_pixels = canvas
        .chunks_exact(4)
        .filter(|pixel| pixel[3] > 0 && pixel[0] < 120 && pixel[1] < 120 && pixel[2] < 120)
        .count();
    let dark_in_band = |start_y: usize, end_y: usize| {
        canvas
            .chunks_exact(4)
            .enumerate()
            .filter(|(index, pixel)| {
                let y = index / 90;
                y >= start_y
                    && y < end_y
                    && pixel[3] > 0
                    && pixel[0] < 120
                    && pixel[1] < 120
                    && pixel[2] < 120
            })
            .count()
    };
    assert!(opaque > 2_000, "bubble and glyphs should be visible");
    assert!(dark_glyph_pixels > 80, "Chinese glyphs should be visible");
    assert!(dark_in_band(3, 20) > 40, "first line should be visible");
    assert!(dark_in_band(20, 38) > 20, "second line should be visible");
}

#[test]
fn native_prompt_bubble_adapts_long_text_to_three_lines() {
    let path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc";
    if !std::path::Path::new(path).is_file() {
        return;
    }
    let font = fontdue::Font::from_bytes(
        fs::read(path).expect("read Noto CJK"),
        fontdue::FontSettings::default(),
    )
    .expect("decode Noto CJK collection");
    let mut canvas = vec![0_u8; 90 * 130 * 4];
    paint_native_prompt_bubble(
        &mut canvas,
        90,
        130,
        "这里是一条较长的自适应提示文本",
        &font,
        255,
    );
    let dark_third_line = canvas
        .chunks_exact(4)
        .enumerate()
        .filter(|(index, pixel)| {
            let y = index / 90;
            (35..54).contains(&y)
                && pixel[3] > 0
                && pixel[0] < 120
                && pixel[1] < 120
                && pixel[2] < 120
        })
        .count();
    assert!(
        dark_third_line > 20,
        "third adaptive line should be visible"
    );
}

#[test]
fn native_transparent_options_default_to_overlay_probe_shape() {
    let opts = NativeTransparentOptions::default();

    assert_eq!(opts.title, DEFAULT_NATIVE_TRANSPARENT_TITLE);
    assert_eq!(opts.width, 360);
    assert_eq!(opts.height, 520);
    assert_eq!(opts.layer, NativeLayer::Overlay);
    assert_eq!(opts.anchor, NativeAnchor::BottomRight);
    assert_eq!(opts.margin_right, 96);
    assert_eq!(opts.margin_bottom, 96);
    assert_eq!(opts.duration_ms, 2_000);
    assert_eq!(
        opts.sprite_asset.as_deref(),
        Some("xiao-shu-v3-ai-idle-breathe-v1")
    );
    assert_eq!(opts.cell_width, DEFAULT_NATIVE_SPRITE_CELL_WIDTH);
    assert_eq!(opts.cell_height, DEFAULT_NATIVE_SPRITE_CELL_HEIGHT);
    assert_eq!(opts.frame_count, DEFAULT_NATIVE_FRAME_COUNT);
    assert_eq!(opts.frame_interval_ms, DEFAULT_NATIVE_FRAME_INTERVAL_MS);
}

#[test]
fn native_transparent_probe_frame_keeps_corners_fully_transparent() {
    let mut canvas = vec![0xff; 96 * 96 * 4];

    paint_transparent_probe_frame(&mut canvas, 96, 96);

    assert_eq!(&canvas[0..4], &argb8888_le(0, 0, 0, 0));
    assert_eq!(
        &canvas[(95 * 96 + 95) * 4..(95 * 96 + 95) * 4 + 4],
        &argb8888_le(0, 0, 0, 0)
    );
}

#[test]
fn native_transparent_probe_frame_draws_an_opaque_marker() {
    let mut canvas = vec![0; 96 * 96 * 4];

    paint_transparent_probe_frame(&mut canvas, 96, 96);

    let bbox = alpha_bbox(&canvas, 96, 96).expect("opaque marker bbox");

    assert!(bbox.min_x > 0);
    assert!(bbox.min_y > 0);
    assert!(bbox.max_x < 95);
    assert!(bbox.max_y < 95);

    let center = ((48 * 96 + 48) * 4) as usize;
    assert_eq!(canvas[center + 3], 0xff);
}

#[test]
fn argb8888_le_uses_premultiplied_wayland_byte_order() {
    assert_eq!(
        argb8888_le(0xaa, 0x11, 0x22, 0x33),
        [0x33, 0x22, 0x11, 0xaa]
    );
}

#[test]
fn native_transparent_plan_describes_read_only_layer_shell_probe() {
    let opts = NativeTransparentOptions {
        width: 240,
        height: 320,
        duration_ms: 750,
        ..NativeTransparentOptions::default()
    };

    let plan = native_transparent_plan_json(&opts, false);

    assert_eq!(plan["surface"], "linux_avatar_native_transparent_plan");
    assert_eq!(plan["backend"], "wayland_wlr_layer_shell");
    assert_eq!(plan["read_only"], true);
    assert_eq!(plan["transparent"], true);
    assert_eq!(plan["spawned"], false);
    assert_eq!(plan["width"], 240);
    assert_eq!(plan["height"], 320);
    assert_eq!(plan["duration_ms"], 750);
    assert_eq!(plan["pixel_format"], "wl_shm::Argb8888");
    assert_eq!(plan["sprite"]["asset"], "xiao-shu-v3-ai-idle-breathe-v1");
    assert_eq!(plan["sprite"]["cell_width"], 192);
    assert_eq!(plan["sprite"]["cell_height"], 208);
    assert_eq!(plan["sprite"]["frame_count"], DEFAULT_NATIVE_FRAME_COUNT);
    assert_eq!(
        plan["sprite"]["frame_interval_ms"],
        DEFAULT_NATIVE_FRAME_INTERVAL_MS
    );
    assert_eq!(plan["state_poll"]["enabled"], false);
    assert_eq!(plan["safety"]["controls_desktop"], false);
}

#[test]
fn native_transparent_plan_describes_draggable_xdg_toplevel() {
    let opts = NativeTransparentOptions {
        width: 90,
        height: 130,
        sprite_scale_percent: 39,
        draggable: true,
        ..NativeTransparentOptions::default()
    };

    let plan = native_transparent_plan_json(&opts, false);

    assert_eq!(plan["backend"], "wayland_xdg_toplevel");
    assert_eq!(plan["draggable"], true);
    assert_eq!(plan["width"], 90);
    assert_eq!(plan["height"], 130);
    assert_eq!(plan["sprite"]["scale_percent"], 39);
}

#[test]
fn native_transparent_plan_describes_pet_state_polling_when_enabled() {
    let opts = NativeTransparentOptions {
        state_pet_id: Some("xiao-shu-dev".to_string()),
        state_poll_ms: 250,
        ..NativeTransparentOptions::default()
    };

    let plan = native_transparent_plan_json(&opts, false);

    assert_eq!(plan["state_poll"]["enabled"], true);
    assert_eq!(plan["state_poll"]["source"], "pet_state_sidecar");
    assert_eq!(plan["state_poll"]["pet_id"], "xiao-shu-dev");
    assert_eq!(plan["state_poll"]["poll_ms"], 250);
}

#[test]
fn native_transparent_plan_describes_http_renderer_state_polling_when_enabled() {
    let opts = NativeTransparentOptions {
        state_url: Some(
            "http://127.0.0.1:7878/avatar-surface/linux-renderer-state?project=agent-bridge"
                .to_string(),
        ),
        state_poll_ms: 200,
        state_http_timeout_ms: 350,
        ..NativeTransparentOptions::default()
    };

    let plan = native_transparent_plan_json(&opts, false);

    assert_eq!(plan["state_poll"]["enabled"], true);
    assert_eq!(plan["state_poll"]["source"], "http_renderer_state");
    assert_eq!(
        plan["state_poll"]["url"],
        "http://127.0.0.1:7878/avatar-surface/linux-renderer-state?project=agent-bridge"
    );
    assert!(plan["state_poll"]["pet_id"].is_null());
    assert_eq!(plan["state_poll"]["poll_ms"], 200);
    assert_eq!(plan["state_poll"]["http_timeout_ms"], 350);
}

#[test]
fn native_transparent_plan_prefers_http_state_over_pet_sidecar_when_both_are_set() {
    let opts = NativeTransparentOptions {
        state_pet_id: Some("xiao-shu-dev".to_string()),
        state_url: Some("http://127.0.0.1:7878/avatar-surface/linux-renderer-state".to_string()),
        ..NativeTransparentOptions::default()
    };

    let plan = native_transparent_plan_json(&opts, false);

    assert_eq!(plan["state_poll"]["enabled"], true);
    assert_eq!(plan["state_poll"]["source"], "http_renderer_state");
    assert_eq!(
        plan["state_poll"]["url"],
        "http://127.0.0.1:7878/avatar-surface/linux-renderer-state"
    );
    assert_eq!(plan["state_poll"]["pet_id"], "xiao-shu-dev");
}

#[test]
fn native_state_http_request_parts_parse_http_url_with_query() {
    let parts = native_state_http_request_parts(
        "http://127.0.0.1:7878/avatar-surface/linux-renderer-state?project=agent-bridge",
    )
    .expect("parse local renderer-state URL");

    assert_eq!(parts.host, "127.0.0.1");
    assert_eq!(parts.port, 7878);
    assert_eq!(parts.host_header, "127.0.0.1:7878");
    assert_eq!(
        parts.path_and_query,
        "/avatar-surface/linux-renderer-state?project=agent-bridge"
    );
}

#[test]
fn native_state_http_request_parts_rejects_https_for_sync_probe() {
    assert!(native_state_http_request_parts("https://127.0.0.1/state").is_err());
}

#[test]
fn native_layer_and_anchor_parse_cli_values() {
    assert_eq!(parse_native_layer("top"), Some(NativeLayer::Top));
    assert_eq!(parse_native_layer("overlay"), Some(NativeLayer::Overlay));
    assert_eq!(parse_native_layer("bad"), None);

    assert_eq!(parse_native_anchor("top-left"), Some(NativeAnchor::TopLeft));
    assert_eq!(
        parse_native_anchor("top-right"),
        Some(NativeAnchor::TopRight)
    );
    assert_eq!(
        parse_native_anchor("bottom-left"),
        Some(NativeAnchor::BottomLeft)
    );
    assert_eq!(
        parse_native_anchor("bottom-right"),
        Some(NativeAnchor::BottomRight)
    );
    assert_eq!(
        parse_native_anchor("bottom_right"),
        Some(NativeAnchor::BottomRight)
    );
    assert_eq!(parse_native_anchor("center"), None);
}

#[test]
fn sidecar_asset_id_is_extracted_from_renderer_asset_route() {
    assert_eq!(
        sidecar_asset_id_from_route(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"
        ),
        Some("xiao-shu-v3-ai-idle-breathe-v1".to_string())
    );
    assert_eq!(
        sidecar_asset_id_from_route(
            "/avatar-surface/sidecar-spritesheet?ignored=1&asset=xiao-shu-v3-ai-completion-nod-v2"
        ),
        Some("xiao-shu-v3-ai-completion-nod-v2".to_string())
    );
    assert_eq!(sidecar_asset_id_from_route("/avatar-surface/panel"), None);
}

#[test]
fn sidecar_sprite_asset_decodes_known_png_atlas() {
    let sprite = decode_sidecar_sprite_asset("xiao-shu-v3-ai-idle-breathe-v1")
        .expect("decode known sidecar atlas");

    assert_eq!(sprite.width, 1536);
    assert_eq!(sprite.height, 1872);
    assert_eq!(sprite.rgba.len(), 1536 * 1872 * 4);
}

#[test]
fn sidecar_sprite_asset_decodes_focus_wave_atlas() {
    let sprite = decode_sidecar_sprite_asset("xiao-shu-v3-focus-wave-v1")
        .expect("decode Xiao Shu focus wave atlas");

    assert_eq!(sprite.width, 1152);
    assert_eq!(sprite.height, 208);
    assert_eq!(sprite.rgba.len(), 1152 * 208 * 4);
    assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] == 0));
    assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] > 0));
}

#[test]
fn sidecar_sprite_asset_decodes_normalized_completion_nod_atlas() {
    let sprite = decode_sidecar_sprite_asset("xiao-shu-v3-ai-completion-nod-v2")
        .expect("decode normalized Xiao Shu completion nod atlas");

    assert_eq!(sprite.width, 1536);
    assert_eq!(sprite.height, 208);
    assert_eq!(sprite.rgba.len(), 1536 * 208 * 4);
    assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] == 0));
    assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] > 0));
}

#[test]
fn sidecar_sprite_assets_decode_paired_focus_turn_atlases() {
    for asset in [
        "xiao-shu-v3-focus-turn-left-v1",
        "xiao-shu-v3-focus-turn-right-v1",
    ] {
        let sprite = decode_sidecar_sprite_asset(asset).expect("decode Xiao Shu focus turn atlas");
        assert_eq!((sprite.width, sprite.height), (1152, 208));
        assert_eq!(sprite.rgba.len(), 1152 * 208 * 4);
        assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] == 0));
        assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] > 0));

        let plan = native_sprite_plan_from_state_value(&json!({
            "state": {"mode": "orienting"},
            "plan": {"asset_route": format!("/avatar-surface/sidecar-spritesheet?asset={asset}")}
        }));
        assert_eq!(plan.frame_count, 6);
    }
}

#[test]
fn sidecar_sprite_assets_decode_paired_focus_walk_atlases() {
    for asset in [
        "xiao-shu-v3-focus-walk-left-v1",
        "xiao-shu-v3-focus-walk-right-v1",
    ] {
        let sprite = decode_sidecar_sprite_asset(asset).expect("decode Xiao Shu focus walk atlas");
        assert_eq!((sprite.width, sprite.height), (1536, 208));
        assert_eq!(sprite.rgba.len(), 1536 * 208 * 4);
        assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] == 0));
        assert!(sprite.rgba.chunks_exact(4).any(|pixel| pixel[3] > 0));

        let plan = native_sprite_plan_from_state_value(&json!({
            "state": {"mode": "working"},
            "plan": {"asset_route": format!("/avatar-surface/sidecar-spritesheet?asset={asset}")}
        }));
        assert_eq!(plan.frame_count, 8);
        assert_eq!(plan.frame_interval_ms, 140);
    }
}

#[test]
fn rgba_sprite_paints_centered_over_transparent_argb_canvas() {
    let sprite = RgbaSprite {
        width: 2,
        height: 2,
        rgba: vec![
            255, 0, 0, 255, // opaque red
            0, 255, 0, 128, // half green
            0, 0, 255, 0, // transparent blue
            255, 255, 0, 255, // opaque yellow
        ],
    };
    let mut canvas = vec![0; 4 * 4 * 4];

    paint_rgba_sprite_centered(&mut canvas, 4, 4, &sprite, 1.0).expect("paint sprite");

    assert_eq!(
        &canvas[((1 * 4 + 1) * 4)..((1 * 4 + 1) * 4 + 4)],
        &argb8888_le(255, 255, 0, 0)
    );
    assert_eq!(
        &canvas[((1 * 4 + 2) * 4)..((1 * 4 + 2) * 4 + 4)],
        &argb8888_le(128, 0, 128, 0)
    );
    assert_eq!(
        &canvas[((2 * 4 + 1) * 4)..((2 * 4 + 1) * 4 + 4)],
        &argb8888_le(0, 0, 0, 0)
    );
    assert_eq!(
        &canvas[((2 * 4 + 2) * 4)..((2 * 4 + 2) * 4 + 4)],
        &argb8888_le(255, 255, 255, 0)
    );
}

#[test]
fn sprite_cell_extracts_one_atlas_frame() {
    let atlas = RgbaSprite {
        width: 4,
        height: 4,
        rgba: (0..64).collect(),
    };

    let cell = sprite_cell(&atlas, 2, 2, 1, 1).expect("extract bottom-right cell");

    assert_eq!(cell.width, 2);
    assert_eq!(cell.height, 2);
    assert_eq!(
        cell.rgba,
        vec![40, 41, 42, 43, 44, 45, 46, 47, 56, 57, 58, 59, 60, 61, 62, 63]
    );
}

#[test]
fn sprite_paint_accepts_wayland_pool_padding() {
    let sprite = RgbaSprite {
        width: 1,
        height: 1,
        rgba: vec![255, 0, 0, 255],
    };
    let mut canvas = vec![0; 2 * 2 * 4 + 64];

    paint_rgba_sprite_centered(&mut canvas, 2, 2, &sprite, 1.0)
        .expect("paint into padded Wayland pool allocation");
    paint_transparent_probe_frame(&mut canvas, 2, 2);

    assert!(canvas[2 * 2 * 4..].iter().all(|byte| *byte == 0));
}

#[test]
fn animation_frame_index_advances_by_interval_and_wraps() {
    assert_eq!(animation_frame_index(0, 4, 120), 0);
    assert_eq!(animation_frame_index(119, 4, 120), 0);
    assert_eq!(animation_frame_index(120, 4, 120), 1);
    assert_eq!(animation_frame_index(359, 4, 120), 2);
    assert_eq!(animation_frame_index(480, 4, 120), 0);
}

#[test]
fn animated_frame_coords_walks_atlas_cells_from_base_frame() {
    assert_eq!(animated_frame_coords(0, 0, 4, 0, 120, 8), (0, 0));
    assert_eq!(animated_frame_coords(0, 0, 4, 120, 120, 8), (1, 0));
    assert_eq!(animated_frame_coords(0, 0, 4, 360, 120, 8), (3, 0));
}

#[test]
fn animated_frame_coords_wraps_to_next_atlas_row() {
    assert_eq!(animated_frame_coords(6, 0, 4, 0, 120, 8), (6, 0));
    assert_eq!(animated_frame_coords(6, 0, 4, 120, 120, 8), (7, 0));
    assert_eq!(animated_frame_coords(6, 0, 4, 240, 120, 8), (0, 1));
    assert_eq!(animated_frame_coords(6, 0, 4, 360, 120, 8), (1, 1));
}

#[test]
fn native_sprite_asset_follows_renderer_mode_with_png_fallbacks() {
    assert_eq!(
        native_sprite_asset_for_mode("idle").as_deref(),
        Some("xiao-shu-v3-ai-idle-breathe-v1")
    );
    assert_eq!(
        native_sprite_asset_for_mode("verified").as_deref(),
        Some("xiao-shu-v3-ai-completion-nod-v2")
    );
    assert_eq!(
        native_sprite_asset_for_mode("working").as_deref(),
        Some("xiao-shu-v3-ai-soft-bounce-v1")
    );
}

#[test]
fn native_sprite_plan_maps_raw_pet_state_to_png_asset_and_timing() {
    let state = json!({
        "mode": "working",
        "activity_state": "implementing"
    });

    let plan = native_sprite_plan_from_state_value(&state);

    assert_eq!(plan.mode, "working");
    assert_eq!(plan.asset.as_deref(), Some("xiao-shu-v3-ai-soft-bounce-v1"));
    assert_eq!(plan.frame_count, 6);
    assert_eq!(plan.frame_interval_ms, 160);
}

#[test]
fn native_sprite_plan_uses_renderer_payload_png_route_when_available() {
    let payload = json!({
        "state": {
            "mode": "verified"
        },
        "plan": {
            "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-completion-nod-v2"
        }
    });

    let plan = native_sprite_plan_from_state_value(&payload);

    assert_eq!(plan.mode, "verified");
    assert_eq!(
        plan.asset.as_deref(),
        Some("xiao-shu-v3-ai-completion-nod-v2")
    );
}

#[test]
fn native_sprite_plan_falls_back_when_renderer_payload_route_is_svg_only() {
    let payload = json!({
        "state": {
            "mode": "working"
        },
        "plan": {
            "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v3"
        }
    });

    let plan = native_sprite_plan_from_state_value(&payload);

    assert_eq!(plan.asset.as_deref(), Some("xiao-shu-v3-ai-soft-bounce-v1"));
}

#[test]
fn native_sprite_plan_updates_transparent_options_without_moving_window() {
    let mut opts = NativeTransparentOptions {
        width: 240,
        height: 320,
        margin_right: 42,
        sprite_scale_percent: 140,
        ..NativeTransparentOptions::default()
    };
    let plan = native_sprite_plan_from_state_value(&json!({ "mode": "verified" }));

    let changed = apply_native_sprite_plan(&mut opts, &plan);

    assert!(changed);
    assert_eq!(opts.width, 240);
    assert_eq!(opts.height, 320);
    assert_eq!(opts.margin_right, 42);
    assert_eq!(opts.sprite_scale_percent, 140);
    assert_eq!(
        opts.sprite_asset.as_deref(),
        Some("xiao-shu-v3-ai-completion-nod-v2")
    );
    assert_eq!(opts.frame_count, 8);
    assert_eq!(opts.frame_interval_ms, 160);
}
