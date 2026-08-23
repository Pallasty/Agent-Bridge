use anyhow::{Context, Result};
use serde::Serialize;
use std::{fs::File, io::BufReader, path::Path};

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
    pub failures: Vec<String>,
}

pub fn audit_sprite_asset(
    path: &Path,
    columns: u32,
    rows: u32,
    cell_width: u32,
    cell_height: u32,
) -> Result<SpriteAssetAudit> {
    anyhow::ensure!(columns > 0 && rows > 0, "sprite grid must be non-zero");
    anyhow::ensure!(
        cell_width > 0 && cell_height > 0,
        "sprite cells must be non-zero"
    );

    let file = File::open(path).with_context(|| format!("open PNG {}", path.display()))?;
    let decoder = png::Decoder::new(BufReader::new(file));
    let mut reader = decoder.read_info().context("read PNG header")?;
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).context("decode PNG")?;
    let expected_width = columns.saturating_mul(cell_width);
    let expected_height = rows.saturating_mul(cell_height);
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
    let mut visible_pixels_per_frame = vec![0_u64; (columns * rows) as usize];
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
                    visible_pixels_per_frame[(row * columns + col) as usize] += 1;
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
        let report = audit_sprite_asset(&path, 2, 1, 2, 2).unwrap();
        std::fs::remove_file(path).unwrap();
        assert!(report.accepted, "{:?}", report.failures);
        assert_eq!(report.visible_pixels_per_frame, vec![1, 1]);
    }

    #[test]
    fn rejects_rgb_preview_and_wrong_geometry() {
        let path = write_png(png::ColorType::Rgb, 3, 2, &[255; 3 * 2 * 3]);
        let report = audit_sprite_asset(&path, 2, 1, 2, 2).unwrap();
        std::fs::remove_file(path).unwrap();
        assert!(!report.accepted);
        assert_eq!(report.failures.len(), 2);
    }
}
