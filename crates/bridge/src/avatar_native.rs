//! Native Linux transparent avatar probe helpers.
//!
//! The browser floater is useful as a renderer fallback, but true desktop
//! transparency needs an alpha-capable native surface. This module keeps the
//! pure planning and pixel code separate from the Wayland runtime glue so the
//! contract is testable without a compositor.

use std::io::Cursor;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, bail, Context};
use serde_json::{json, Value};

pub const DEFAULT_NATIVE_TRANSPARENT_TITLE: &str = "Linux Codex Avatar Native Transparent Probe";
pub const DEFAULT_NATIVE_SPRITE_ASSET: &str = "xiao-shu-v3-ai-idle-breathe-v1";
pub const DEFAULT_NATIVE_SPRITE_CELL_WIDTH: u32 = 192;
pub const DEFAULT_NATIVE_SPRITE_CELL_HEIGHT: u32 = 208;
pub const DEFAULT_NATIVE_SPRITE_SCALE_PERCENT: u32 = 155;
pub const DEFAULT_NATIVE_FRAME_COUNT: u32 = 6;
pub const DEFAULT_NATIVE_FRAME_INTERVAL_MS: u64 = 180;
pub const DEFAULT_NATIVE_STATE_POLL_MS: u64 = 500;
#[cfg(all(target_os = "linux", feature = "linux-native-avatar"))]
pub const NATIVE_FEATURE_CONTRACT: &str = "agent_bridge.avatar.native_linux.v1";
#[cfg(not(all(target_os = "linux", feature = "linux-native-avatar")))]
pub const NATIVE_FEATURE_CONTRACT: &str = "agent_bridge.avatar.native_linux.uncompiled.v1";
pub const DEFAULT_NATIVE_STATE_HTTP_TIMEOUT_MS: u64 = 800;
pub const NATIVE_MOTION_OVERRIDE_FILE: &str = "ab-face-motion-override.json";
pub const NATIVE_MOTION_OVERRIDE_SCHEMA: &str = "agent_bridge.avatar_native_motion_override.v1";
pub const NATIVE_PROMPT_FILE: &str = "ab-avatar-prompt.json";
pub const NATIVE_PROMPT_SCHEMA: &str = "agent_bridge.avatar_native_prompt.v1";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativePromptPlan {
    pub text: String,
    pub expires_at_unix_ms: u64,
}

pub fn default_native_prompt_path() -> Option<PathBuf> {
    std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .map(|path| path.join(NATIVE_PROMPT_FILE))
}

pub fn native_prompt_plan(path: &Path) -> anyhow::Result<Option<NativePromptPlan>> {
    let bytes = match std::fs::read(path) {
        Ok(bytes) => bytes,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(err) => {
            return Err(err).with_context(|| format!("read native prompt {}", path.display()))
        }
    };
    let value: Value = serde_json::from_slice(&bytes)
        .with_context(|| format!("decode native prompt {}", path.display()))?;
    if value.get("schema").and_then(Value::as_str) != Some(NATIVE_PROMPT_SCHEMA) {
        bail!("native prompt schema is missing or unsupported");
    }
    let expires_at_unix_ms = value
        .get("expires_at_unix_ms")
        .and_then(Value::as_u64)
        .context("native prompt is missing expires_at_unix_ms")?;
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64;
    if expires_at_unix_ms <= now {
        return Ok(None);
    }
    let text = value
        .get("text")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|text| !text.is_empty() && text.chars().count() <= 32)
        .context("native prompt text must contain 1 through 32 characters")?;
    Ok(Some(NativePromptPlan {
        text: text.to_string(),
        expires_at_unix_ms,
    }))
}

pub fn default_native_motion_override_path() -> Option<PathBuf> {
    std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .map(|path| path.join(NATIVE_MOTION_OVERRIDE_FILE))
}

pub fn native_motion_override_plan(path: &Path) -> anyhow::Result<Option<NativeSpritePlan>> {
    match std::fs::read(path) {
        Ok(bytes) => {
            let value: Value = serde_json::from_slice(&bytes)
                .with_context(|| format!("decode native motion override {}", path.display()))?;
            if value.get("schema").and_then(Value::as_str) != Some(NATIVE_MOTION_OVERRIDE_SCHEMA) {
                bail!("native motion override schema is missing or unsupported");
            }
            let expires_at = value
                .get("expires_at_unix_ms")
                .and_then(Value::as_u64)
                .context("native motion override is missing expires_at_unix_ms")?;
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64;
            if expires_at <= now {
                return Ok(None);
            }
            Ok(Some(native_sprite_plan_from_state_value(&value)))
        }
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(err) => {
            Err(err).with_context(|| format!("read native motion override {}", path.display()))
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NativeLayer {
    Top,
    Overlay,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NativeAnchor {
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativeTransparentOptions {
    pub title: String,
    pub width: u32,
    pub height: u32,
    pub layer: NativeLayer,
    pub anchor: NativeAnchor,
    pub margin_top: i32,
    pub margin_right: i32,
    pub margin_bottom: i32,
    pub margin_left: i32,
    pub duration_ms: u64,
    pub sprite_asset: Option<String>,
    pub frame_col: u32,
    pub frame_row: u32,
    pub cell_width: u32,
    pub cell_height: u32,
    pub sprite_scale_percent: u32,
    pub frame_count: u32,
    pub frame_interval_ms: u64,
    pub state_pet_id: Option<String>,
    pub state_url: Option<String>,
    pub state_poll_ms: u64,
    pub state_http_timeout_ms: u64,
    /// Wayland output to place the layer surface on, by name (e.g. "DP-1").
    /// None = the compositor's default output.
    pub output: Option<String>,
    /// Use a transparent XDG toplevel so the compositor can move the avatar.
    pub draggable: bool,
}

impl Default for NativeTransparentOptions {
    fn default() -> Self {
        Self {
            title: DEFAULT_NATIVE_TRANSPARENT_TITLE.to_string(),
            width: 360,
            height: 520,
            layer: NativeLayer::Overlay,
            anchor: NativeAnchor::BottomRight,
            margin_top: 0,
            margin_right: 96,
            margin_bottom: 96,
            margin_left: 0,
            duration_ms: 2_000,
            sprite_asset: Some(DEFAULT_NATIVE_SPRITE_ASSET.to_string()),
            frame_col: 0,
            frame_row: 0,
            cell_width: DEFAULT_NATIVE_SPRITE_CELL_WIDTH,
            cell_height: DEFAULT_NATIVE_SPRITE_CELL_HEIGHT,
            sprite_scale_percent: DEFAULT_NATIVE_SPRITE_SCALE_PERCENT,
            frame_count: DEFAULT_NATIVE_FRAME_COUNT,
            frame_interval_ms: DEFAULT_NATIVE_FRAME_INTERVAL_MS,
            state_pet_id: None,
            state_url: None,
            state_poll_ms: DEFAULT_NATIVE_STATE_POLL_MS,
            state_http_timeout_ms: DEFAULT_NATIVE_STATE_HTTP_TIMEOUT_MS,
            output: None,
            draggable: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativeSpritePlan {
    pub mode: String,
    pub asset: Option<String>,
    pub frame_col: u32,
    pub frame_row: u32,
    pub frame_count: u32,
    pub frame_interval_ms: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AlphaBBox {
    pub min_x: u32,
    pub min_y: u32,
    pub max_x: u32,
    pub max_y: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RgbaSprite {
    pub width: u32,
    pub height: u32,
    pub rgba: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NativeStateHttpRequestParts {
    pub host: String,
    pub port: u16,
    pub host_header: String,
    pub path_and_query: String,
}

pub fn native_state_http_request_parts(url: &str) -> anyhow::Result<NativeStateHttpRequestParts> {
    let parsed = reqwest::Url::parse(url).with_context(|| format!("parse state URL {url}"))?;
    if parsed.scheme() != "http" {
        bail!("native transparent state URL only supports plain http endpoints");
    }

    let host = parsed
        .host_str()
        .map(ToOwned::to_owned)
        .context("native transparent state URL is missing a host")?;
    let port = parsed
        .port_or_known_default()
        .context("native transparent state URL is missing a port")?;
    let host_header = match parsed.port() {
        Some(port) => format!("{host}:{port}"),
        None => host.clone(),
    };
    let mut path_and_query = if parsed.path().is_empty() {
        "/".to_string()
    } else {
        parsed.path().to_string()
    };
    if let Some(query) = parsed.query() {
        path_and_query.push('?');
        path_and_query.push_str(query);
    }

    Ok(NativeStateHttpRequestParts {
        host,
        port,
        host_header,
        path_and_query,
    })
}

pub fn argb8888_le(alpha: u8, red: u8, green: u8, blue: u8) -> [u8; 4] {
    let value = ((alpha as u32) << 24) | ((red as u32) << 16) | ((green as u32) << 8) | blue as u32;
    value.to_le_bytes()
}

pub fn sidecar_asset_id_from_route(route: &str) -> Option<String> {
    let query = route.split_once('?')?.1;
    query.split('&').find_map(|part| {
        let (key, value) = part.split_once('=')?;
        (key == "asset" && !value.trim().is_empty()).then(|| value.trim().to_string())
    })
}

pub fn sidecar_sprite_asset_png(asset: &str) -> Option<&'static [u8]> {
    match asset {
        "xiao-shu-ai-alert-peek-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-ai-alert-peek-v1-atlas.png"
        )),
        "xiao-shu-ai-alert-peek-v2" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-ai-alert-peek-v2-atlas.png"
        )),
        "xiao-shu-v3-alert-peek-sheet-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-alert-peek-sheet-v1-atlas.png"
        )),
        "xiao-shu-v3-ai-alert-peek-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v1-atlas.png"
        )),
        "xiao-shu-v3-ai-alert-peek-v2" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v2-atlas.png"
        )),
        "xiao-shu-v3-ai-alert-peek-v3" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v3-atlas.png"
        )),
        "xiao-shu-v3-ai-idle-breathe-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-idle-breathe-v1-atlas.png"
        )),
        "xiao-shu-v3-ai-soft-bounce-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-soft-bounce-v1-atlas.png"
        )),
        "xiao-shu-v3-ai-completion-nod-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v1-atlas.png"
        )),
        "xiao-shu-v3-ai-completion-nod-v2" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v2-atlas.png"
        )),
        "xiao-shu-v3-focus-wave-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-wave-v1-atlas.png"
        )),
        "xiao-shu-v3-focus-turn-left-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-turn-left-v1-atlas.png"
        )),
        "xiao-shu-v3-focus-turn-right-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-turn-right-v1-atlas.png"
        )),
        "xiao-shu-v3-focus-walk-left-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-walk-left-v1-atlas.png"
        )),
        "xiao-shu-v3-focus-walk-right-v1" => Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-walk-right-v1-atlas.png"
        )),
        _ => None,
    }
}

pub fn native_sprite_asset_for_mode(mode: &str) -> Option<String> {
    let state = json!({ "mode": mode });
    let plan = crate::avatar_renderer::renderer_plan_from_state(&state);
    if let Some(asset) = plan
        .asset_route
        .as_deref()
        .and_then(sidecar_asset_id_from_route)
        .filter(|asset| sidecar_sprite_asset_png(asset).is_some())
    {
        return Some(asset);
    }

    let fallback = match mode {
        "verified" => "xiao-shu-v3-ai-completion-nod-v2",
        "working" => "xiao-shu-v3-ai-soft-bounce-v1",
        "orienting" | "reviewing" | "waiting_for_user" | "failed" => "xiao-shu-v3-ai-alert-peek-v3",
        _ => DEFAULT_NATIVE_SPRITE_ASSET,
    };
    Some(fallback.to_string())
}

fn native_non_empty_str<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

fn native_state_from_state_value(value: &Value) -> &Value {
    value
        .get("state")
        .filter(|state| state.is_object())
        .unwrap_or(value)
}

fn native_asset_from_renderer_payload(value: &Value) -> Option<String> {
    value
        .get("plan")
        .and_then(|plan| plan.get("asset_route"))
        .and_then(Value::as_str)
        .and_then(sidecar_asset_id_from_route)
        .filter(|asset| sidecar_sprite_asset_png(asset).is_some())
}

pub fn native_frame_timing_for_mode(mode: &str) -> (u32, u64) {
    match mode {
        "working" | "verified" => (6, 160),
        "orienting" | "reviewing" | "waiting_for_user" | "failed" => (8, 160),
        _ => (DEFAULT_NATIVE_FRAME_COUNT, DEFAULT_NATIVE_FRAME_INTERVAL_MS),
    }
}

pub fn native_sprite_plan_from_state_value(value: &Value) -> NativeSpritePlan {
    let state = native_state_from_state_value(value);
    let mode = native_non_empty_str(state, "mode").unwrap_or("idle");
    let asset =
        native_asset_from_renderer_payload(value).or_else(|| native_sprite_asset_for_mode(mode));
    let (frame_count, frame_interval_ms) = match asset.as_deref() {
        Some("xiao-shu-v3-ai-completion-nod-v1" | "xiao-shu-v3-ai-completion-nod-v2") => (8, 160),
        Some("xiao-shu-v3-focus-turn-left-v1" | "xiao-shu-v3-focus-turn-right-v1") => (6, 160),
        Some("xiao-shu-v3-focus-walk-left-v1" | "xiao-shu-v3-focus-walk-right-v1") => (8, 140),
        _ => native_frame_timing_for_mode(mode),
    };
    NativeSpritePlan {
        mode: mode.to_string(),
        asset,
        frame_col: 0,
        frame_row: 0,
        frame_count,
        frame_interval_ms,
    }
}

pub fn apply_native_sprite_plan(
    opts: &mut NativeTransparentOptions,
    plan: &NativeSpritePlan,
) -> bool {
    let changed = opts.sprite_asset != plan.asset
        || opts.frame_col != plan.frame_col
        || opts.frame_row != plan.frame_row
        || opts.frame_count != plan.frame_count
        || opts.frame_interval_ms != plan.frame_interval_ms;
    opts.sprite_asset = plan.asset.clone();
    opts.frame_col = plan.frame_col;
    opts.frame_row = plan.frame_row;
    opts.frame_count = plan.frame_count;
    opts.frame_interval_ms = plan.frame_interval_ms;
    changed
}

pub fn decode_sidecar_sprite_asset(asset: &str) -> anyhow::Result<RgbaSprite> {
    let bytes = sidecar_sprite_asset_png(asset)
        .ok_or_else(|| anyhow!("unknown sidecar sprite asset: {asset}"))?;
    decode_png_rgba(bytes).with_context(|| format!("decode sidecar sprite asset {asset}"))
}

pub fn decode_png_rgba(bytes: &[u8]) -> anyhow::Result<RgbaSprite> {
    let decoder = png::Decoder::new(Cursor::new(bytes));
    let mut reader = decoder.read_info().context("read PNG header")?;
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).context("decode PNG frame")?;
    let pixels = &buf[..info.buffer_size()];
    let rgba = match (info.color_type, info.bit_depth) {
        (png::ColorType::Rgba, png::BitDepth::Eight) => pixels.to_vec(),
        (png::ColorType::Rgb, png::BitDepth::Eight) => {
            let mut out = Vec::with_capacity(info.width as usize * info.height as usize * 4);
            for rgb in pixels.chunks_exact(3) {
                out.extend_from_slice(&[rgb[0], rgb[1], rgb[2], 0xff]);
            }
            out
        }
        other => anyhow::bail!("unsupported PNG color format: {other:?}"),
    };

    Ok(RgbaSprite {
        width: info.width,
        height: info.height,
        rgba,
    })
}

pub fn sprite_cell(
    atlas: &RgbaSprite,
    cell_width: u32,
    cell_height: u32,
    frame_col: u32,
    frame_row: u32,
) -> anyhow::Result<RgbaSprite> {
    if atlas.rgba.len() != atlas.width as usize * atlas.height as usize * 4 {
        anyhow::bail!("RGBA atlas length must match width * height * 4");
    }
    let origin_x = frame_col
        .checked_mul(cell_width)
        .ok_or_else(|| anyhow!("sprite frame column overflow"))?;
    let origin_y = frame_row
        .checked_mul(cell_height)
        .ok_or_else(|| anyhow!("sprite frame row overflow"))?;
    if origin_x + cell_width > atlas.width || origin_y + cell_height > atlas.height {
        anyhow::bail!("sprite frame is outside atlas bounds");
    }

    let mut rgba = Vec::with_capacity(cell_width as usize * cell_height as usize * 4);
    for y in 0..cell_height {
        let src = (((origin_y + y) * atlas.width + origin_x) * 4) as usize;
        let end = src + cell_width as usize * 4;
        rgba.extend_from_slice(&atlas.rgba[src..end]);
    }

    Ok(RgbaSprite {
        width: cell_width,
        height: cell_height,
        rgba,
    })
}

pub fn animation_frame_index(elapsed_ms: u64, frame_count: u32, frame_interval_ms: u64) -> u32 {
    let frame_count = frame_count.max(1);
    let frame_interval_ms = frame_interval_ms.max(1);
    ((elapsed_ms / frame_interval_ms) % frame_count as u64) as u32
}

pub fn animated_frame_coords(
    base_col: u32,
    base_row: u32,
    frame_count: u32,
    elapsed_ms: u64,
    frame_interval_ms: u64,
    atlas_columns: u32,
) -> (u32, u32) {
    let atlas_columns = atlas_columns.max(1);
    let frame_index = animation_frame_index(elapsed_ms, frame_count, frame_interval_ms);
    let linear = base_row
        .saturating_mul(atlas_columns)
        .saturating_add(base_col)
        .saturating_add(frame_index);
    (linear % atlas_columns, linear / atlas_columns)
}

pub fn sprite_atlas_columns(atlas: &RgbaSprite, cell_width: u32) -> u32 {
    atlas.width / cell_width.max(1)
}

pub fn paint_rgba_sprite_centered(
    canvas: &mut [u8],
    width: u32,
    height: u32,
    sprite: &RgbaSprite,
    scale: f32,
) -> anyhow::Result<()> {
    paint_rgba_sprite_centered_with_y_offset(canvas, width, height, sprite, scale, 0)
}

pub fn paint_rgba_sprite_centered_with_y_offset(
    canvas: &mut [u8],
    width: u32,
    height: u32,
    sprite: &RgbaSprite,
    scale: f32,
    y_offset: i32,
) -> anyhow::Result<()> {
    let expected_len = width as usize * height as usize * 4;
    if canvas.len() < expected_len {
        anyhow::bail!("ARGB8888 canvas length must cover width * height * 4");
    }
    if sprite.rgba.len() != sprite.width as usize * sprite.height as usize * 4 {
        anyhow::bail!("RGBA sprite length must match width * height * 4");
    }
    if !(scale.is_finite() && scale > 0.0) {
        anyhow::bail!("sprite scale must be positive and finite");
    }

    let dest_w = ((sprite.width as f32 * scale).round() as u32).max(1);
    let dest_h = ((sprite.height as f32 * scale).round() as u32).max(1);
    let origin_x = (width as i32 - dest_w as i32) / 2;
    let origin_y = (height as i32 - dest_h as i32) / 2 + y_offset;

    for dy in 0..dest_h {
        let y = origin_y + dy as i32;
        if y < 0 || y >= height as i32 {
            continue;
        }
        let src_y = ((dy as f32 / scale).floor() as u32).min(sprite.height - 1);
        for dx in 0..dest_w {
            let x = origin_x + dx as i32;
            if x < 0 || x >= width as i32 {
                continue;
            }
            let src_x = ((dx as f32 / scale).floor() as u32).min(sprite.width - 1);
            let src_offset = ((src_y * sprite.width + src_x) * 4) as usize;
            let red = sprite.rgba[src_offset];
            let green = sprite.rgba[src_offset + 1];
            let blue = sprite.rgba[src_offset + 2];
            let alpha = sprite.rgba[src_offset + 3];
            let premul =
                |channel: u8| -> u8 { ((channel as u16 * alpha as u16 + 127) / 255) as u8 };
            let dest_offset = (((y as u32) * width + x as u32) * 4) as usize;
            canvas[dest_offset..dest_offset + 4].copy_from_slice(&argb8888_le(
                alpha,
                premul(red),
                premul(green),
                premul(blue),
            ));
        }
    }

    Ok(())
}

fn blend_argb8888_pixel(canvas: &mut [u8], width: u32, x: i32, y: i32, rgba: [u8; 4]) {
    if x < 0 || y < 0 || x >= width as i32 {
        return;
    }
    let offset = ((y as u32 * width + x as u32) * 4) as usize;
    if offset + 4 > canvas.len() {
        return;
    }
    let a = rgba[3] as u16;
    let inv = 255 - a;
    let old_b = canvas[offset] as u16;
    let old_g = canvas[offset + 1] as u16;
    let old_r = canvas[offset + 2] as u16;
    let old_a = canvas[offset + 3] as u16;
    canvas[offset] = ((rgba[2] as u16 * a + old_b * inv) / 255) as u8;
    canvas[offset + 1] = ((rgba[1] as u16 * a + old_g * inv) / 255) as u8;
    canvas[offset + 2] = ((rgba[0] as u16 * a + old_r * inv) / 255) as u8;
    canvas[offset + 3] = (a + old_a * inv / 255).min(255) as u8;
}

pub fn paint_native_prompt_bubble(
    canvas: &mut [u8],
    width: u32,
    height: u32,
    text: &str,
    font: &fontdue::Font,
) {
    if width < 48 || height < 48 {
        return;
    }
    let left = 2_i32;
    let right = width as i32 - 3;
    let top = 2_i32;
    let bottom = 43_i32.min(height as i32 - 8);
    let radius = 7_i32;
    for y in top..=bottom {
        for x in left..=right {
            let cx = x.clamp(left + radius, right - radius);
            let cy = y.clamp(top + radius, bottom - radius);
            if (x - cx).pow(2) + (y - cy).pow(2) <= radius.pow(2) {
                blend_argb8888_pixel(canvas, width, x, y, [255, 250, 238, 238]);
            }
        }
    }
    let mid = width as i32 / 2;
    for dy in 0..6_i32 {
        for dx in -dy..=dy {
            blend_argb8888_pixel(canvas, width, mid + dx, bottom + dy, [255, 250, 238, 238]);
        }
    }
    let chars: Vec<char> = text.chars().collect();
    let split = chars.len().min(5);
    let lines = [&chars[..split], &chars[split..]];
    for (line_index, line) in lines.into_iter().enumerate() {
        if line.is_empty() {
            continue;
        }
        let px = 12.0_f32;
        let widths: Vec<usize> = line
            .iter()
            .map(|c| font.metrics(*c, px).advance_width.ceil() as usize)
            .collect();
        let line_width: usize = widths.iter().sum();
        let mut pen_x = ((width as usize).saturating_sub(line_width) / 2) as i32;
        // fontdue's ymin is relative to the baseline. Keep both baselines far
        // enough below the bubble top that CJK ascenders remain on-canvas.
        let baseline_y = 16 + line_index as i32 * 15;
        for (ch, advance) in line.iter().zip(widths) {
            let (metrics, bitmap) = font.rasterize(*ch, px);
            for gy in 0..metrics.height {
                for gx in 0..metrics.width {
                    let alpha = bitmap[gy * metrics.width + gx];
                    blend_argb8888_pixel(
                        canvas,
                        width,
                        pen_x + metrics.xmin + gx as i32,
                        baseline_y - metrics.height as i32 - metrics.ymin + gy as i32,
                        [45, 55, 72, alpha],
                    );
                }
            }
            pen_x += advance as i32;
        }
    }
}

pub fn paint_transparent_probe_frame(canvas: &mut [u8], width: u32, height: u32) {
    let expected_len = width as usize * height as usize * 4;
    assert!(
        canvas.len() >= expected_len,
        "ARGB8888 canvas length must cover width * height * 4"
    );
    let canvas = &mut canvas[..expected_len];

    for chunk in canvas.chunks_exact_mut(4) {
        chunk.copy_from_slice(&argb8888_le(0, 0, 0, 0));
    }

    if width < 16 || height < 16 {
        return;
    }

    let radius = width.min(height) / 5;
    let center_x = width / 2;
    let center_y = height / 2;
    let radius_sq = (radius * radius) as i64;
    let ring_radius = radius + radius / 3;
    let ring_sq = (ring_radius * ring_radius) as i64;

    for y in 0..height {
        for x in 0..width {
            let dx = x as i64 - center_x as i64;
            let dy = y as i64 - center_y as i64;
            let dist_sq = dx * dx + dy * dy;
            let color = if dist_sq <= radius_sq {
                Some(argb8888_le(0xff, 0x4d, 0xd0, 0xe1))
            } else if dist_sq <= ring_sq && dist_sq >= ring_sq - (radius as i64 * 2) {
                Some(argb8888_le(0xdd, 0xff, 0xc8, 0x57))
            } else {
                None
            };

            if let Some(pixel) = color {
                let offset = ((y * width + x) * 4) as usize;
                canvas[offset..offset + 4].copy_from_slice(&pixel);
            }
        }
    }
}

pub fn clear_argb8888(canvas: &mut [u8]) {
    for chunk in canvas.chunks_exact_mut(4) {
        chunk.copy_from_slice(&argb8888_le(0, 0, 0, 0));
    }
}

pub fn alpha_bbox(canvas: &[u8], width: u32, height: u32) -> Option<AlphaBBox> {
    if canvas.len() != width as usize * height as usize * 4 {
        return None;
    }

    let mut bbox: Option<AlphaBBox> = None;
    for y in 0..height {
        for x in 0..width {
            let alpha = canvas[((y * width + x) * 4 + 3) as usize];
            if alpha == 0 {
                continue;
            }

            bbox = Some(match bbox {
                Some(current) => AlphaBBox {
                    min_x: current.min_x.min(x),
                    min_y: current.min_y.min(y),
                    max_x: current.max_x.max(x),
                    max_y: current.max_y.max(y),
                },
                None => AlphaBBox {
                    min_x: x,
                    min_y: y,
                    max_x: x,
                    max_y: y,
                },
            });
        }
    }
    bbox
}

pub fn native_transparent_plan_json(opts: &NativeTransparentOptions, spawned: bool) -> Value {
    let state_source = if opts.state_url.is_some() {
        Some("http_renderer_state")
    } else if opts.state_pet_id.is_some() {
        Some("pet_state_sidecar")
    } else {
        None
    };
    json!({
        "surface": "linux_avatar_native_transparent_plan",
        "backend": if opts.draggable { "wayland_xdg_toplevel" } else { "wayland_wlr_layer_shell" },
        "read_only": true,
        "transparent": true,
        "draggable": opts.draggable,
        "spawned": spawned,
        "title": opts.title,
        "width": opts.width,
        "height": opts.height,
        "layer": native_layer_name(opts.layer),
        "anchor": native_anchor_name(opts.anchor),
        "margin": {
            "top": opts.margin_top,
            "right": opts.margin_right,
            "bottom": opts.margin_bottom,
            "left": opts.margin_left,
        },
        "duration_ms": opts.duration_ms,
        "output": opts.output,
        "pixel_format": "wl_shm::Argb8888",
        "sprite": {
            "asset": opts.sprite_asset,
            "frame_col": opts.frame_col,
            "frame_row": opts.frame_row,
            "cell_width": opts.cell_width,
            "cell_height": opts.cell_height,
            "scale_percent": opts.sprite_scale_percent,
            "frame_count": opts.frame_count,
            "frame_interval_ms": opts.frame_interval_ms,
        },
        "state_poll": {
            "enabled": state_source.is_some(),
            "source": state_source,
            "pet_id": opts.state_pet_id.as_deref(),
            "url": opts.state_url.as_deref(),
            "poll_ms": opts.state_poll_ms,
            "http_timeout_ms": opts.state_http_timeout_ms,
        },
        "safety": {
            "sidecar_only": true,
            "writes_files": false,
            "mutates_renderer": false,
            "codex_pet_package_mutation": false,
            "emits_audio": false,
            "emits_notification": false,
            "controls_desktop": false,
        }
    })
}

pub fn native_layer_name(layer: NativeLayer) -> &'static str {
    match layer {
        NativeLayer::Top => "top",
        NativeLayer::Overlay => "overlay",
    }
}

pub fn native_anchor_name(anchor: NativeAnchor) -> &'static str {
    match anchor {
        NativeAnchor::TopLeft => "top_left",
        NativeAnchor::TopRight => "top_right",
        NativeAnchor::BottomLeft => "bottom_left",
        NativeAnchor::BottomRight => "bottom_right",
    }
}

pub fn parse_native_layer(value: &str) -> Option<NativeLayer> {
    match value.trim().to_ascii_lowercase().as_str() {
        "top" => Some(NativeLayer::Top),
        "overlay" => Some(NativeLayer::Overlay),
        _ => None,
    }
}

pub fn parse_native_anchor(value: &str) -> Option<NativeAnchor> {
    match value.trim().to_ascii_lowercase().replace('_', "-").as_str() {
        "top-left" => Some(NativeAnchor::TopLeft),
        "top-right" => Some(NativeAnchor::TopRight),
        "bottom-left" => Some(NativeAnchor::BottomLeft),
        "bottom-right" => Some(NativeAnchor::BottomRight),
        _ => None,
    }
}

#[cfg(all(target_os = "linux", feature = "linux-native-avatar"))]
pub fn run_native_transparent_probe(opts: NativeTransparentOptions) -> anyhow::Result<()> {
    wayland_probe::run(opts)
}

#[cfg(not(all(target_os = "linux", feature = "linux-native-avatar")))]
pub fn run_native_transparent_probe(_opts: NativeTransparentOptions) -> anyhow::Result<()> {
    #[cfg(target_os = "linux")]
    anyhow::bail!("native transparent probe requires the linux-native-avatar feature on Linux");
    #[cfg(not(target_os = "linux"))]
    anyhow::bail!("native transparent probe is only available on Linux");
}

#[cfg(all(target_os = "linux", feature = "linux-native-avatar"))]
mod wayland_probe {
    use std::io::{Read, Write};
    use std::net::TcpStream;
    use std::num::NonZeroU32;
    use std::path::PathBuf;
    use std::time::{Duration, Instant};

    use anyhow::{bail, Context, Result};
    use smithay_client_toolkit::{
        compositor::{CompositorHandler, CompositorState},
        delegate_compositor, delegate_layer, delegate_output, delegate_registry, delegate_shm,
        delegate_xdg_shell, delegate_xdg_window,
        output::{OutputHandler, OutputState},
        registry::{ProvidesRegistryState, RegistryState},
        registry_handlers,
        shell::{
            wlr_layer::{
                Anchor, KeyboardInteractivity, Layer, LayerShell, LayerShellHandler, LayerSurface,
                LayerSurfaceConfigure,
            },
            xdg::{
                window::{Window, WindowConfigure, WindowDecorations, WindowHandler},
                XdgShell,
            },
            WaylandSurface,
        },
        shm::{slot::SlotPool, Shm, ShmHandler},
    };
    use wayland_client::{
        globals::registry_queue_init,
        protocol::{wl_output, wl_shm, wl_surface},
        Connection, QueueHandle,
    };

    use super::{
        animated_frame_coords, animation_frame_index, clear_argb8888, decode_sidecar_sprite_asset,
        default_native_motion_override_path, default_native_prompt_path,
        native_motion_override_plan, native_prompt_plan, native_sprite_plan_from_state_value,
        native_state_http_request_parts, paint_native_prompt_bubble,
        paint_rgba_sprite_centered_with_y_offset, paint_transparent_probe_frame,
        sprite_atlas_columns, sprite_cell, NativeAnchor, NativeLayer, NativePromptPlan,
        NativeSpritePlan, NativeTransparentOptions, RgbaSprite,
    };

    fn load_prompt_font() -> Option<fontdue::Font> {
        [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        .into_iter()
        .find_map(|path| {
            std::fs::read(path).ok().and_then(|bytes| {
                fontdue::Font::from_bytes(bytes, fontdue::FontSettings::default()).ok()
            })
        })
    }

    pub fn run(opts: NativeTransparentOptions) -> Result<()> {
        let conn = Connection::connect_to_env().context("connect to Wayland compositor")?;
        let (globals, mut event_queue) =
            registry_queue_init(&conn).context("initialize Wayland registry queue")?;
        let qh = event_queue.handle();

        let compositor =
            CompositorState::bind(&globals, &qh).context("bind wl_compositor global")?;
        let layer_shell = if opts.draggable {
            None
        } else {
            Some(LayerShell::bind(&globals, &qh).context(
                "bind zwlr_layer_shell_v1 global; this compositor may not support wlr layer-shell",
            )?)
        };
        let xdg_shell = if opts.draggable {
            Some(XdgShell::bind(&globals, &qh).context("bind xdg_wm_base global")?)
        } else {
            None
        };
        let shm = Shm::bind(&globals, &qh).context("bind wl_shm global")?;

        let sprite_animation = sprite_animation_from_options(&opts)
            .context("load native transparent sprite animation")?;

        let pool_len = (opts.width.max(1) * opts.height.max(1) * 4) as usize * 2;
        let pool = SlotPool::new(pool_len, &shm).context("create Wayland SHM slot pool")?;
        let mut app = NativeProbeApp {
            registry_state: RegistryState::new(&globals),
            output_state: OutputState::new(&globals, &qh),
            shm,
            exit: false,
            configured: false,
            pool,
            width: opts.width,
            height: opts.height,
            sprite_animation,
            started_at: Instant::now(),
            last_frame_index: None,
            cell_width: opts.cell_width,
            cell_height: opts.cell_height,
            sprite_scale_percent: opts.sprite_scale_percent,
            state_pet_id: opts.state_pet_id.clone(),
            state_url: opts.state_url.clone(),
            state_http_timeout: Duration::from_millis(opts.state_http_timeout_ms.max(50)),
            state_poll_interval: Duration::from_millis(opts.state_poll_ms.max(50)),
            next_state_poll_at: Instant::now() + Duration::from_millis(opts.state_poll_ms.max(50)),
            motion_override_path: default_native_motion_override_path(),
            prompt_path: default_native_prompt_path(),
            prompt: None,
            prompt_font: load_prompt_font(),
            layer: None,
            window: None,
        };

        // Enumerate outputs BEFORE binding the layer surface: a layer-shell
        // surface's output is fixed at creation time (it can't be moved later),
        // so we roundtrip to populate OutputState, then resolve --output by name.
        // A few roundtrips let wl_output name events arrive. Falls back to the
        // compositor's default output when unset or not found.
        for _ in 0..3 {
            event_queue
                .roundtrip(&mut app)
                .context("enumerate Wayland outputs")?;
            if app.output_state.outputs().next().is_some() {
                break;
            }
        }
        let target_output = match opts.output.as_deref() {
            Some(want) => {
                let found = app.output_state.outputs().find(|o| {
                    app.output_state.info(o).and_then(|i| i.name).as_deref() == Some(want)
                });
                if found.is_none() {
                    eprintln!(
                        "agent-bridge native transparent: output {want:?} not found; using compositor default"
                    );
                }
                found
            }
            None => None,
        };

        let surface = compositor.create_surface(&qh);
        if let Some(xdg_shell) = xdg_shell {
            let window = xdg_shell.create_window(surface, WindowDecorations::None, &qh);
            window.set_title(opts.title.clone());
            window.set_app_id("agent-bridge-avatar");
            window.set_min_size(Some((opts.width, opts.height)));
            window.set_max_size(Some((opts.width, opts.height)));
            window.commit();
            app.window = Some(window);
        } else {
            let layer = layer_shell
                .expect("layer shell bound for anchored mode")
                .create_layer_surface(
                    &qh,
                    surface,
                    to_sctk_layer(opts.layer),
                    Some("agent-bridge-avatar"),
                    target_output.as_ref(),
                );
            layer.set_anchor(to_sctk_anchor(opts.anchor));
            layer.set_keyboard_interactivity(KeyboardInteractivity::None);
            layer.set_margin(
                opts.margin_top,
                opts.margin_right,
                opts.margin_bottom,
                opts.margin_left,
            );
            layer.set_exclusive_zone(0);
            layer.set_size(opts.width, opts.height);
            layer.commit();
            app.layer = Some(layer);
        }

        while !app.configured && !app.exit {
            event_queue
                .blocking_dispatch(&mut app)
                .context("wait for native surface configure")?;
        }

        let deadline = Instant::now() + Duration::from_millis(opts.duration_ms);
        while !app.exit && Instant::now() < deadline {
            event_queue
                .dispatch_pending(&mut app)
                .context("dispatch Wayland pending events")?;
            if app.poll_state_if_due() || app.draw_if_due() {
                event_queue
                    .roundtrip(&mut app)
                    .context("roundtrip after native transparent redraw")?;
            } else {
                conn.flush().context("flush Wayland connection")?;
            }
            std::thread::sleep(Duration::from_millis(16));
        }

        Ok(())
    }

    struct NativeProbeApp {
        registry_state: RegistryState,
        output_state: OutputState,
        shm: Shm,
        exit: bool,
        configured: bool,
        pool: SlotPool,
        width: u32,
        height: u32,
        sprite_animation: Option<SpriteAnimation>,
        started_at: Instant,
        last_frame_index: Option<u32>,
        cell_width: u32,
        cell_height: u32,
        sprite_scale_percent: u32,
        state_pet_id: Option<String>,
        state_url: Option<String>,
        state_http_timeout: Duration,
        state_poll_interval: Duration,
        next_state_poll_at: Instant,
        motion_override_path: Option<PathBuf>,
        prompt_path: Option<PathBuf>,
        prompt: Option<NativePromptPlan>,
        prompt_font: Option<fontdue::Font>,
        layer: Option<LayerSurface>,
        window: Option<Window>,
    }

    struct SpriteAnimation {
        asset: String,
        atlas: RgbaSprite,
        frame_col: u32,
        frame_row: u32,
        cell_width: u32,
        cell_height: u32,
        frame_count: u32,
        frame_interval_ms: u64,
        sprite_scale_percent: u32,
    }

    fn sprite_animation_from_options(
        opts: &NativeTransparentOptions,
    ) -> Result<Option<SpriteAnimation>> {
        opts.sprite_asset
            .as_deref()
            .map(|asset| {
                sprite_animation_from_parts(
                    asset,
                    opts.frame_col,
                    opts.frame_row,
                    opts.cell_width,
                    opts.cell_height,
                    opts.frame_count,
                    opts.frame_interval_ms,
                    opts.sprite_scale_percent,
                )
            })
            .transpose()
    }

    #[allow(clippy::too_many_arguments)]
    fn sprite_animation_from_parts(
        asset: &str,
        frame_col: u32,
        frame_row: u32,
        cell_width: u32,
        cell_height: u32,
        frame_count: u32,
        frame_interval_ms: u64,
        sprite_scale_percent: u32,
    ) -> Result<SpriteAnimation> {
        let atlas = decode_sidecar_sprite_asset(asset)?;
        Ok(SpriteAnimation {
            asset: asset.to_string(),
            atlas,
            frame_col,
            frame_row,
            cell_width,
            cell_height,
            frame_count,
            frame_interval_ms,
            sprite_scale_percent,
        })
    }

    impl SpriteAnimation {
        fn matches_plan(&self, plan: &NativeSpritePlan) -> bool {
            Some(self.asset.as_str()) == plan.asset.as_deref()
                && self.frame_col == plan.frame_col
                && self.frame_row == plan.frame_row
                && self.frame_count == plan.frame_count
                && self.frame_interval_ms == plan.frame_interval_ms
        }
    }

    impl NativeProbeApp {
        fn draw(&mut self) -> bool {
            if let Err(err) = self.try_draw() {
                eprintln!("agent-bridge native transparent probe draw failed: {err:#}");
                self.exit = true;
                return false;
            }
            true
        }

        fn poll_state_if_due(&mut self) -> bool {
            if self.state_url.is_none()
                && self.state_pet_id.is_none()
                && self.motion_override_path.is_none()
                && self.prompt_path.is_none()
            {
                return false;
            }
            let now = Instant::now();
            if now < self.next_state_poll_at {
                return false;
            }
            self.next_state_poll_at = now + self.state_poll_interval;

            let next_prompt =
                self.prompt_path
                    .as_deref()
                    .and_then(|path| match native_prompt_plan(path) {
                        Ok(plan) => plan,
                        Err(err) => {
                            eprintln!(
                                "agent-bridge native prompt poll failed for {}: {err:#}",
                                path.display()
                            );
                            None
                        }
                    });
            let prompt_changed = next_prompt != self.prompt;
            self.prompt = next_prompt;

            if let Some(path) = self.motion_override_path.clone() {
                match native_motion_override_plan(&path) {
                    Ok(Some(plan)) => {
                        return self.apply_sprite_plan(&plan) || (prompt_changed && self.draw());
                    }
                    Ok(None) => {}
                    Err(err) => {
                        eprintln!(
                            "agent-bridge native transparent motion override failed for {}: {err:#}",
                            path.display()
                        );
                    }
                }
            }

            if let Some(url) = self.state_url.clone() {
                match self.fetch_http_sprite_plan(&url) {
                    Ok(plan) => {
                        return self.apply_sprite_plan(&plan) || (prompt_changed && self.draw())
                    }
                    Err(err) => {
                        eprintln!(
                            "agent-bridge native transparent probe HTTP state poll failed for {url}: {err:#}"
                        );
                    }
                }
            }

            let Some(pet_id) = self.state_pet_id.clone() else {
                return prompt_changed && self.draw();
            };
            match crate::pet_state::read_pet_state(&pet_id) {
                Ok(Some(state)) => {
                    let plan = native_sprite_plan_from_state_value(&state);
                    self.apply_sprite_plan(&plan) || (prompt_changed && self.draw())
                }
                Ok(None) => prompt_changed && self.draw(),
                Err(err) => {
                    eprintln!(
                        "agent-bridge native transparent probe state poll failed for {pet_id}: {err}"
                    );
                    prompt_changed && self.draw()
                }
            }
        }

        fn fetch_http_sprite_plan(&self, url: &str) -> Result<NativeSpritePlan> {
            let parts = native_state_http_request_parts(url)?;
            let mut stream = TcpStream::connect((parts.host.as_str(), parts.port))
                .with_context(|| format!("connect to renderer-state endpoint {url}"))?;
            stream
                .set_read_timeout(Some(self.state_http_timeout))
                .context("set renderer-state read timeout")?;
            stream
                .set_write_timeout(Some(self.state_http_timeout))
                .context("set renderer-state write timeout")?;
            let request = format!(
                "GET {} HTTP/1.1\r\nHost: {}\r\nAccept: application/json\r\nConnection: close\r\n\r\n",
                parts.path_and_query, parts.host_header
            );
            stream
                .write_all(request.as_bytes())
                .with_context(|| format!("send renderer-state request to {url}"))?;
            stream
                .flush()
                .with_context(|| format!("flush renderer-state request to {url}"))?;

            let mut response = String::new();
            stream
                .read_to_string(&mut response)
                .with_context(|| format!("read renderer-state response from {url}"))?;
            let (head, body) = response
                .split_once("\r\n\r\n")
                .context("renderer-state response is missing HTTP headers")?;
            let status_line = head
                .lines()
                .next()
                .context("renderer-state response is missing a status line")?;
            let status = status_line
                .split_whitespace()
                .nth(1)
                .context("renderer-state response status line is malformed")?;
            if !status.starts_with('2') {
                bail!("renderer-state endpoint returned HTTP {status}");
            }

            let value: serde_json::Value = serde_json::from_str(body)
                .with_context(|| format!("decode renderer-state JSON from {url}"))?;
            Ok(native_sprite_plan_from_state_value(&value))
        }

        fn apply_sprite_plan(&mut self, plan: &NativeSpritePlan) -> bool {
            let changed = match (&self.sprite_animation, plan.asset.as_deref()) {
                (Some(current), Some(_)) => !current.matches_plan(plan),
                (None, Some(_)) | (Some(_), None) => true,
                (None, None) => false,
            };
            if !changed {
                return false;
            }

            let next = match plan.asset.as_deref() {
                Some(asset) => match sprite_animation_from_parts(
                    asset,
                    plan.frame_col,
                    plan.frame_row,
                    self.cell_width,
                    self.cell_height,
                    plan.frame_count,
                    plan.frame_interval_ms,
                    self.sprite_scale_percent,
                ) {
                    Ok(animation) => Some(animation),
                    Err(err) => {
                        eprintln!(
                            "agent-bridge native transparent probe state plan failed for mode={}: {err:#}",
                            plan.mode
                        );
                        return false;
                    }
                },
                None => None,
            };

            self.sprite_animation = next;
            self.started_at = Instant::now();
            self.last_frame_index = None;
            self.draw()
        }

        fn draw_if_due(&mut self) -> bool {
            let Some(animation) = &self.sprite_animation else {
                return false;
            };
            let elapsed_ms = self.elapsed_ms();
            let frame_index = animation_frame_index(
                elapsed_ms,
                animation.frame_count,
                animation.frame_interval_ms,
            );
            if self.last_frame_index != Some(frame_index) {
                return self.draw();
            }
            false
        }

        fn elapsed_ms(&self) -> u64 {
            self.started_at
                .elapsed()
                .as_millis()
                .try_into()
                .unwrap_or(u64::MAX)
        }

        fn try_draw(&mut self) -> Result<()> {
            let width = self.width.max(1);
            let height = self.height.max(1);
            let sprite_to_paint = self
                .sprite_animation
                .as_ref()
                .map(|animation| {
                    let elapsed_ms = self.elapsed_ms();
                    let frame_index = animation_frame_index(
                        elapsed_ms,
                        animation.frame_count,
                        animation.frame_interval_ms,
                    );
                    let atlas_columns =
                        sprite_atlas_columns(&animation.atlas, animation.cell_width);
                    let (frame_col, frame_row) = animated_frame_coords(
                        animation.frame_col,
                        animation.frame_row,
                        animation.frame_count,
                        elapsed_ms,
                        animation.frame_interval_ms,
                        atlas_columns,
                    );
                    let sprite = sprite_cell(
                        &animation.atlas,
                        animation.cell_width,
                        animation.cell_height,
                        frame_col,
                        frame_row,
                    )?;
                    Ok::<_, anyhow::Error>((
                        sprite,
                        animation.sprite_scale_percent as f32 / 100.0,
                        frame_index,
                    ))
                })
                .transpose()?;
            let stride = width as i32 * 4;
            let (buffer, canvas) = self
                .pool
                .create_buffer(
                    width as i32,
                    height as i32,
                    stride,
                    wl_shm::Format::Argb8888,
                )
                .context("create ARGB8888 Wayland buffer")?;

            if let Some((sprite, scale, frame_index)) = sprite_to_paint {
                clear_argb8888(canvas);
                let y_offset = if self.prompt.is_some() { 18 } else { 0 };
                paint_rgba_sprite_centered_with_y_offset(
                    canvas, width, height, &sprite, scale, y_offset,
                )?;
                self.last_frame_index = Some(frame_index);
            } else {
                paint_transparent_probe_frame(canvas, width, height);
            }
            if let (Some(prompt), Some(font)) = (&self.prompt, &self.prompt_font) {
                paint_native_prompt_bubble(canvas, width, height, &prompt.text, font);
            }
            let surface = self
                .layer
                .as_ref()
                .map(WaylandSurface::wl_surface)
                .or_else(|| self.window.as_ref().map(WaylandSurface::wl_surface))
                .expect("native surface initialized before draw");
            surface.damage_buffer(0, 0, width as i32, height as i32);
            buffer
                .attach_to(surface)
                .context("attach ARGB8888 buffer")?;
            surface.commit();
            Ok(())
        }
    }

    impl CompositorHandler for NativeProbeApp {
        fn scale_factor_changed(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _surface: &wl_surface::WlSurface,
            _new_factor: i32,
        ) {
        }

        fn transform_changed(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _surface: &wl_surface::WlSurface,
            _new_transform: wl_output::Transform,
        ) {
        }

        fn frame(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _surface: &wl_surface::WlSurface,
            _time: u32,
        ) {
        }

        fn surface_enter(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _surface: &wl_surface::WlSurface,
            _output: &wl_output::WlOutput,
        ) {
        }

        fn surface_leave(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _surface: &wl_surface::WlSurface,
            _output: &wl_output::WlOutput,
        ) {
        }
    }

    impl OutputHandler for NativeProbeApp {
        fn output_state(&mut self) -> &mut OutputState {
            &mut self.output_state
        }

        fn new_output(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _output: wl_output::WlOutput,
        ) {
        }

        fn update_output(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _output: wl_output::WlOutput,
        ) {
        }

        fn output_destroyed(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _output: wl_output::WlOutput,
        ) {
        }
    }

    impl LayerShellHandler for NativeProbeApp {
        fn closed(&mut self, _conn: &Connection, _qh: &QueueHandle<Self>, _layer: &LayerSurface) {
            self.exit = true;
        }

        fn configure(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _layer: &LayerSurface,
            configure: LayerSurfaceConfigure,
            _serial: u32,
        ) {
            self.width = NonZeroU32::new(configure.new_size.0).map_or(self.width, NonZeroU32::get);
            self.height =
                NonZeroU32::new(configure.new_size.1).map_or(self.height, NonZeroU32::get);
            self.configured = true;
            self.draw();
        }
    }

    impl WindowHandler for NativeProbeApp {
        fn request_close(&mut self, _conn: &Connection, _qh: &QueueHandle<Self>, _window: &Window) {
            self.exit = true;
        }

        fn configure(
            &mut self,
            _conn: &Connection,
            _qh: &QueueHandle<Self>,
            _window: &Window,
            configure: WindowConfigure,
            _serial: u32,
        ) {
            self.width = configure.new_size.0.map_or(self.width, NonZeroU32::get);
            self.height = configure.new_size.1.map_or(self.height, NonZeroU32::get);
            self.configured = true;
            self.draw();
        }
    }

    impl ShmHandler for NativeProbeApp {
        fn shm_state(&mut self) -> &mut Shm {
            &mut self.shm
        }
    }

    fn to_sctk_layer(layer: NativeLayer) -> Layer {
        match layer {
            NativeLayer::Top => Layer::Top,
            NativeLayer::Overlay => Layer::Overlay,
        }
    }

    fn to_sctk_anchor(anchor: NativeAnchor) -> Anchor {
        match anchor {
            NativeAnchor::TopLeft => Anchor::TOP | Anchor::LEFT,
            NativeAnchor::TopRight => Anchor::TOP | Anchor::RIGHT,
            NativeAnchor::BottomLeft => Anchor::BOTTOM | Anchor::LEFT,
            NativeAnchor::BottomRight => Anchor::BOTTOM | Anchor::RIGHT,
        }
    }

    delegate_compositor!(NativeProbeApp);
    delegate_output!(NativeProbeApp);
    delegate_shm!(NativeProbeApp);
    delegate_layer!(NativeProbeApp);
    delegate_xdg_shell!(NativeProbeApp);
    delegate_xdg_window!(NativeProbeApp);
    delegate_registry!(NativeProbeApp);

    impl ProvidesRegistryState for NativeProbeApp {
        fn registry(&mut self) -> &mut RegistryState {
            &mut self.registry_state
        }

        registry_handlers![OutputState];
    }
}
