use anyhow::{Context, Result};
use serde::Serialize;
use std::{fs::File, io::BufReader, path::Path};

pub const FOCUS_FOLLOW_ASSET_CONTRACT_SCHEMA: &str =
    "agent_bridge.avatar_focus_follow_asset_contract.v1";

#[derive(Debug, Clone, Copy, Serialize)]
pub struct FocusFollowAssetSpec {
    pub action: &'static str,
    pub filename: &'static str,
    pub columns: u32,
    pub rows: u32,
    pub frame_count: u32,
    pub cell_width: u32,
    pub cell_height: u32,
    pub target_width: u32,
    pub target_height: u32,
    pub max_baseline_drift_px: u32,
    pub frame_sequence: &'static [&'static str],
}

const WAVE_FRAMES: &[&str] = &["neutral", "raise", "out", "in", "out", "settle"];
const TURN_LEFT_FRAMES: &[&str] = &[
    "front",
    "quarter",
    "profile",
    "profile_hold",
    "quarter",
    "front",
];
const TURN_RIGHT_FRAMES: &[&str] = &[
    "front",
    "quarter",
    "profile",
    "profile_hold",
    "quarter",
    "front",
];
const WALK_FRAMES: &[&str] = &[
    "contact", "down", "passing", "up", "contact", "down", "passing", "up",
];

pub const FOCUS_FOLLOW_ASSET_SPECS: [FocusFollowAssetSpec; 5] = [
    FocusFollowAssetSpec {
        action: "wave",
        filename: "xiao-shu-v3-focus-wave-v1-atlas.png",
        columns: 6,
        rows: 1,
        frame_count: 6,
        cell_width: 192,
        cell_height: 208,
        target_width: 90,
        target_height: 130,
        max_baseline_drift_px: 8,
        frame_sequence: WAVE_FRAMES,
    },
    FocusFollowAssetSpec {
        action: "turn_left",
        filename: "xiao-shu-v3-focus-turn-left-v1-atlas.png",
        columns: 6,
        rows: 1,
        frame_count: 6,
        cell_width: 192,
        cell_height: 208,
        target_width: 90,
        target_height: 130,
        max_baseline_drift_px: 8,
        frame_sequence: TURN_LEFT_FRAMES,
    },
    FocusFollowAssetSpec {
        action: "turn_right",
        filename: "xiao-shu-v3-focus-turn-right-v1-atlas.png",
        columns: 6,
        rows: 1,
        frame_count: 6,
        cell_width: 192,
        cell_height: 208,
        target_width: 90,
        target_height: 130,
        max_baseline_drift_px: 8,
        frame_sequence: TURN_RIGHT_FRAMES,
    },
    FocusFollowAssetSpec {
        action: "walk_left",
        filename: "xiao-shu-v3-focus-walk-left-v1-atlas.png",
        columns: 8,
        rows: 1,
        frame_count: 8,
        cell_width: 192,
        cell_height: 208,
        target_width: 90,
        target_height: 130,
        max_baseline_drift_px: 16,
        frame_sequence: WALK_FRAMES,
    },
    FocusFollowAssetSpec {
        action: "walk_right",
        filename: "xiao-shu-v3-focus-walk-right-v1-atlas.png",
        columns: 8,
        rows: 1,
        frame_count: 8,
        cell_width: 192,
        cell_height: 208,
        target_width: 90,
        target_height: 130,
        max_baseline_drift_px: 16,
        frame_sequence: WALK_FRAMES,
    },
];

#[derive(Debug, Serialize)]
pub struct FocusFollowAssetStatus {
    pub spec: FocusFollowAssetSpec,
    pub path: String,
    pub status: String,
    pub audit: Option<SpriteAssetAudit>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct FocusFollowAssetContract {
    pub schema: &'static str,
    pub asset_root: String,
    pub ready: bool,
    pub accepted: usize,
    pub missing: usize,
    pub rejected: usize,
    pub assets: Vec<FocusFollowAssetStatus>,
}

pub fn focus_follow_asset_contract(asset_root: &Path) -> FocusFollowAssetContract {
    let mut assets = Vec::with_capacity(FOCUS_FOLLOW_ASSET_SPECS.len());
    for spec in FOCUS_FOLLOW_ASSET_SPECS {
        let path = asset_root.join(spec.filename);
        let (status, audit, error) = if !path.is_file() {
            ("missing", None, None)
        } else {
            match audit_sprite_asset(
                &path,
                spec.columns,
                spec.rows,
                spec.cell_width,
                spec.cell_height,
                Some(spec.frame_count),
                spec.target_width,
                spec.target_height,
                spec.max_baseline_drift_px,
            ) {
                Ok(report) if report.accepted => ("accepted", Some(report), None),
                Ok(report) => ("rejected", Some(report), None),
                Err(err) => ("rejected", None, Some(format!("{err:#}"))),
            }
        };
        assets.push(FocusFollowAssetStatus {
            spec,
            path: path.display().to_string(),
            status: status.to_string(),
            audit,
            error,
        });
    }
    let accepted = assets
        .iter()
        .filter(|item| item.status == "accepted")
        .count();
    let missing = assets
        .iter()
        .filter(|item| item.status == "missing")
        .count();
    let rejected = assets
        .iter()
        .filter(|item| item.status == "rejected")
        .count();
    FocusFollowAssetContract {
        schema: FOCUS_FOLLOW_ASSET_CONTRACT_SCHEMA,
        asset_root: asset_root.display().to_string(),
        ready: accepted == assets.len(),
        accepted,
        missing,
        rejected,
        assets,
    }
}

#[derive(Debug, Serialize)]
pub struct SpriteFrameAudit {
    pub index: u32,
    pub visible_pixels: u64,
    pub bounds_xywh: Option<[u32; 4]>,
    pub baseline_y: Option<u32>,
    pub projected_bounds_wh: Option<[u32; 2]>,
}

#[derive(Debug, Serialize)]
pub struct SpriteAssetAudit {
    pub path: String,
    pub accepted: bool,
    pub width: u32,
    pub height: u32,
    pub color_type: String,
    pub bit_depth: String,
    pub expected_width: u32,
    pub expected_height: u32,
    pub transparent_pixels: u64,
    pub visible_pixels_per_frame: Vec<u64>,
    pub frame_count: u32,
    pub target_width: u32,
    pub target_height: u32,
    pub baseline_drift_px: u32,
    pub frames: Vec<SpriteFrameAudit>,
    pub failures: Vec<String>,
}

pub fn audit_sprite_asset(
    path: &Path,
    columns: u32,
    rows: u32,
    cell_width: u32,
    cell_height: u32,
    frame_count: Option<u32>,
    target_width: u32,
    target_height: u32,
    max_baseline_drift_px: u32,
) -> Result<SpriteAssetAudit> {
    anyhow::ensure!(columns > 0 && rows > 0, "sprite grid must be non-zero");
    anyhow::ensure!(
        cell_width > 0 && cell_height > 0,
        "sprite cells must be non-zero"
    );
    anyhow::ensure!(
        target_width > 0 && target_height > 0,
        "target size must be non-zero"
    );
    let cell_count = columns
        .checked_mul(rows)
        .context("sprite grid cell count overflow")?;
    let frame_count = frame_count.unwrap_or(cell_count);
    anyhow::ensure!(
        frame_count > 0 && frame_count <= cell_count,
        "frame count must fit the grid"
    );

    let file = File::open(path).with_context(|| format!("open PNG {}", path.display()))?;
    let decoder = png::Decoder::new(BufReader::new(file));
    let mut reader = decoder.read_info().context("read PNG header")?;
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).context("decode PNG")?;
    let expected_width = columns
        .checked_mul(cell_width)
        .context("sprite atlas width overflow")?;
    let expected_height = rows
        .checked_mul(cell_height)
        .context("sprite atlas height overflow")?;
    let mut failures = Vec::new();

    if info.color_type != png::ColorType::Rgba || info.bit_depth != png::BitDepth::Eight {
        failures.push("PNG must use 8-bit RGBA; RGB/checkerboard previews are rejected".into());
    }
    if info.width != expected_width || info.height != expected_height {
        failures.push(format!(
            "atlas geometry must be {expected_width}x{expected_height}, got {}x{}",
            info.width, info.height
        ));
    }

    let mut transparent_pixels = 0_u64;
    let mut visible_pixels_per_frame = vec![0_u64; frame_count as usize];
    let mut bounds = vec![None::<[u32; 4]>; frame_count as usize];
    if info.color_type == png::ColorType::Rgba && info.bit_depth == png::BitDepth::Eight {
        let pixels = &buf[..info.buffer_size()];
        for y in 0..info.height {
            for x in 0..info.width {
                let alpha = pixels[((y * info.width + x) * 4 + 3) as usize];
                if alpha == 0 {
                    transparent_pixels += 1;
                }
                if alpha > 0 && x < expected_width && y < expected_height {
                    let col = x / cell_width;
                    let row = y / cell_height;
                    let frame = row * columns + col;
                    if frame < frame_count {
                        visible_pixels_per_frame[frame as usize] += 1;
                        let local_x = x % cell_width;
                        let local_y = y % cell_height;
                        let bounds = &mut bounds[frame as usize];
                        *bounds = Some(match *bounds {
                            Some([min_x, min_y, max_x, max_y]) => [
                                min_x.min(local_x),
                                min_y.min(local_y),
                                max_x.max(local_x),
                                max_y.max(local_y),
                            ],
                            None => [local_x, local_y, local_x, local_y],
                        });
                    }
                }
            }
        }
        if transparent_pixels == 0 {
            failures.push("atlas has no fully transparent background pixels".into());
        }
        for (index, visible) in visible_pixels_per_frame.iter().enumerate() {
            if *visible == 0 {
                failures.push(format!("frame {index} contains no visible pixels"));
            }
        }
    }

    let baselines: Vec<u32> = bounds.iter().filter_map(|b| b.map(|v| v[3])).collect();
    let baseline_drift_px = baselines
        .iter()
        .max()
        .zip(baselines.iter().min())
        .map(|(max, min)| max - min)
        .unwrap_or(0);
    if baseline_drift_px > max_baseline_drift_px {
        failures.push(format!(
            "frame baseline drift is {baseline_drift_px}px, limit is {max_baseline_drift_px}px"
        ));
    }
    let frames = bounds
        .iter()
        .enumerate()
        .map(|(index, bounds)| {
            let bounds_xywh = bounds.map(|[min_x, min_y, max_x, max_y]| {
                [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1]
            });
            let projected_bounds_wh = bounds_xywh.map(|[_, _, width, height]| {
                [
                    ((u64::from(width) * u64::from(target_width)).div_ceil(u64::from(cell_width)))
                        as u32,
                    ((u64::from(height) * u64::from(target_height))
                        .div_ceil(u64::from(cell_height))) as u32,
                ]
            });
            SpriteFrameAudit {
                index: index as u32,
                visible_pixels: visible_pixels_per_frame[index],
                bounds_xywh,
                baseline_y: bounds.map(|v| v[3]),
                projected_bounds_wh,
            }
        })
        .collect();

    Ok(SpriteAssetAudit {
        path: path.display().to_string(),
        accepted: failures.is_empty(),
        width: info.width,
        height: info.height,
        color_type: format!("{:?}", info.color_type),
        bit_depth: format!("{:?}", info.bit_depth),
        expected_width,
        expected_height,
        transparent_pixels,
        visible_pixels_per_frame,
        frame_count,
        target_width,
        target_height,
        baseline_drift_px,
        frames,
        failures,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn write_png(
        color: png::ColorType,
        width: u32,
        height: u32,
        pixels: &[u8],
    ) -> std::path::PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!("ab-avatar-asset-audit-{nonce}.png"));
        let file = File::create(&path).unwrap();
        let mut encoder = png::Encoder::new(file, width, height);
        encoder.set_color(color);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().unwrap();
        writer.write_image_data(pixels).unwrap();
        writer.finish().unwrap();
        path
    }

    #[test]
    fn accepts_rgba_atlas_with_transparency_and_visible_frames() {
        let mut pixels = vec![0_u8; 4 * 2 * 4];
        for x in [0_usize, 2] {
            pixels[x * 4..x * 4 + 4].copy_from_slice(&[1, 2, 3, 255]);
        }
        let path = write_png(png::ColorType::Rgba, 4, 2, &pixels);
        let report = audit_sprite_asset(&path, 2, 1, 2, 2, None, 90, 130, 1).unwrap();
        std::fs::remove_file(path).unwrap();
        assert!(report.accepted, "{:?}", report.failures);
        assert_eq!(report.visible_pixels_per_frame, vec![1, 1]);
    }

    #[test]
    fn rejects_rgb_preview_and_wrong_geometry() {
        let path = write_png(png::ColorType::Rgb, 3, 2, &[255; 3 * 2 * 3]);
        let report = audit_sprite_asset(&path, 2, 1, 2, 2, None, 90, 130, 1).unwrap();
        std::fs::remove_file(path).unwrap();
        assert!(!report.accepted);
        assert_eq!(report.failures.len(), 2);
    }

    #[test]
    fn audits_only_declared_populated_frames_and_reports_baseline_drift() {
        let mut pixels = vec![0_u8; 4 * 4 * 4];
        pixels[3] = 255;
        pixels[(2 * 4) * 4 + 3] = 255;
        let path = write_png(png::ColorType::Rgba, 4, 4, &pixels);
        let report = audit_sprite_asset(&path, 2, 2, 2, 2, Some(3), 90, 130, 0).unwrap();
        std::fs::remove_file(path).unwrap();
        assert!(!report.accepted);
        assert_eq!(report.visible_pixels_per_frame, vec![1, 0, 1]);
        assert_eq!(report.baseline_drift_px, 0);
        assert!(report.failures.iter().any(|item| item.contains("frame 1")));
        assert!(!report.failures.iter().any(|item| item.contains("frame 3")));
    }

    #[test]
    fn focus_follow_contract_is_complete_and_fail_closed_when_assets_are_missing() {
        let root = std::env::temp_dir().join(format!(
            "ab-avatar-contract-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir(&root).unwrap();
        let contract = focus_follow_asset_contract(&root);
        std::fs::remove_dir(root).unwrap();
        assert!(!contract.ready);
        assert_eq!(contract.accepted, 0);
        assert_eq!(contract.missing, 5);
        assert_eq!(contract.rejected, 0);
        assert_eq!(
            contract
                .assets
                .iter()
                .map(|item| item.spec.action)
                .collect::<Vec<_>>(),
            vec!["wave", "turn_left", "turn_right", "walk_left", "walk_right"]
        );
    }
}
