use anyhow::{Context, Result};
use serde::Serialize;
use std::{fs::File, io::BufReader, path::Path};

#[derive(Debug, Clone, Copy)]
pub struct SpriteCompileOptions {
    pub frame_count: u32,
    pub cell_width: u32,
    pub cell_height: u32,
    pub padding_px: u32,
    pub baseline_y: u32,
}

impl Default for SpriteCompileOptions {
    fn default() -> Self {
        Self {
            frame_count: 6,
            cell_width: 192,
            cell_height: 208,
            padding_px: 6,
            baseline_y: 201,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct SpriteCompileFrame {
    pub index: u32,
    pub source_bounds_xywh: [u32; 4],
    pub output_bounds_xywh: [u32; 4],
}

#[derive(Debug, Serialize)]
pub struct SpriteCompileReport {
    pub input: String,
    pub output: String,
    pub executed: bool,
    pub source_width: u32,
    pub source_height: u32,
    pub output_width: u32,
    pub output_height: u32,
    pub frame_count: u32,
    pub frames: Vec<SpriteCompileFrame>,
}

struct SourceImage {
    width: u32,
    height: u32,
    rgba: Vec<u8>,
}

fn chroma_alpha(r: u8, g: u8, b: u8) -> u8 {
    let r = i32::from(r);
    let g = i32::from(g);
    let b = i32::from(b);
    let magenta = r.min(b) - g;
    let saturation_gate = r.min(b);
    if saturation_gate < 120 || magenta <= 55 {
        return 255;
    }
    if magenta >= 135 && saturation_gate >= 175 {
        return 0;
    }
    let foreground = (135 - magenta).clamp(0, 80) * 255 / 80;
    foreground as u8
}

fn bleed_edge_colors(rgba: &mut [u8], width: u32, height: u32) {
    let source = rgba.to_vec();
    for y in 0..height {
        for x in 0..width {
            let offset = ((y * width + x) * 4) as usize;
            let alpha = source[offset + 3];
            if alpha == 0 {
                rgba[offset..offset + 3].fill(0);
                continue;
            }
            if alpha == 255 {
                continue;
            }
            let mut nearest: Option<(u32, usize)> = None;
            for radius in 1..=6_i32 {
                for dy in -radius..=radius {
                    for dx in -radius..=radius {
                        if dx.abs().max(dy.abs()) != radius {
                            continue;
                        }
                        let sx = x as i32 + dx;
                        let sy = y as i32 + dy;
                        if sx < 0 || sy < 0 || sx >= width as i32 || sy >= height as i32 {
                            continue;
                        }
                        let sample = ((sy as u32 * width + sx as u32) * 4) as usize;
                        if source[sample + 3] == 255 {
                            let distance = (dx * dx + dy * dy) as u32;
                            if nearest.is_none_or(|(best, _)| distance < best) {
                                nearest = Some((distance, sample));
                            }
                        }
                    }
                }
                if nearest.is_some() {
                    break;
                }
            }
            if let Some((_, sample)) = nearest {
                rgba[offset..offset + 3].copy_from_slice(&source[sample..sample + 3]);
            }
        }
    }
}

fn decode_source(path: &Path) -> Result<SourceImage> {
    let file = File::open(path).with_context(|| format!("open source PNG {}", path.display()))?;
    let decoder = png::Decoder::new(BufReader::new(file));
    let mut reader = decoder.read_info().context("read source PNG header")?;
    let mut buf = vec![0; reader.output_buffer_size()];
    let info = reader.next_frame(&mut buf).context("decode source PNG")?;
    anyhow::ensure!(
        info.bit_depth == png::BitDepth::Eight,
        "source PNG must use 8-bit channels"
    );
    let pixels = &buf[..info.buffer_size()];
    let mut rgba = Vec::with_capacity(info.width as usize * info.height as usize * 4);
    match info.color_type {
        png::ColorType::Rgb => {
            for pixel in pixels.chunks_exact(3) {
                let alpha = chroma_alpha(pixel[0], pixel[1], pixel[2]);
                rgba.extend_from_slice(&[pixel[0], pixel[1], pixel[2], alpha]);
            }
        }
        png::ColorType::Rgba => {
            for pixel in pixels.chunks_exact(4) {
                let keyed = chroma_alpha(pixel[0], pixel[1], pixel[2]);
                let alpha = pixel[3].min(keyed);
                rgba.extend_from_slice(&[pixel[0], pixel[1], pixel[2], alpha]);
            }
        }
        other => anyhow::bail!("source PNG must be RGB or RGBA, got {other:?}"),
    }
    bleed_edge_colors(&mut rgba, info.width, info.height);
    Ok(SourceImage {
        width: info.width,
        height: info.height,
        rgba,
    })
}

fn alpha_bounds(source: &SourceImage, x0: u32, x1: u32) -> Option<[u32; 4]> {
    let mut bounds: Option<[u32; 4]> = None;
    for y in 0..source.height {
        for x in x0..x1 {
            let alpha = source.rgba[((y * source.width + x) * 4 + 3) as usize];
            if alpha <= 8 {
                continue;
            }
            bounds = Some(match bounds {
                Some([min_x, min_y, max_x, max_y]) => {
                    [min_x.min(x), min_y.min(y), max_x.max(x), max_y.max(y)]
                }
                None => [x, y, x, y],
            });
        }
    }
    bounds.map(|[min_x, min_y, max_x, max_y]| [min_x, min_y, max_x - min_x + 1, max_y - min_y + 1])
}

fn sample_bilinear(source: &SourceImage, x: f32, y: f32) -> [u8; 4] {
    let x0 = x.floor().clamp(0.0, (source.width - 1) as f32) as u32;
    let y0 = y.floor().clamp(0.0, (source.height - 1) as f32) as u32;
    let x1 = (x0 + 1).min(source.width - 1);
    let y1 = (y0 + 1).min(source.height - 1);
    let tx = x - x0 as f32;
    let ty = y - y0 as f32;
    let taps = [
        (x0, y0, (1.0 - tx) * (1.0 - ty)),
        (x1, y0, tx * (1.0 - ty)),
        (x0, y1, (1.0 - tx) * ty),
        (x1, y1, tx * ty),
    ];
    let mut alpha = 0.0_f32;
    let mut premul = [0.0_f32; 3];
    for (sx, sy, weight) in taps {
        let offset = ((sy * source.width + sx) * 4) as usize;
        let a = f32::from(source.rgba[offset + 3]) / 255.0;
        alpha += a * weight;
        for channel in 0..3 {
            premul[channel] += f32::from(source.rgba[offset + channel]) * a * weight;
        }
    }
    if alpha <= f32::EPSILON {
        return [0, 0, 0, 0];
    }
    [
        (premul[0] / alpha).round().clamp(0.0, 255.0) as u8,
        (premul[1] / alpha).round().clamp(0.0, 255.0) as u8,
        (premul[2] / alpha).round().clamp(0.0, 255.0) as u8,
        (alpha * 255.0).round().clamp(0.0, 255.0) as u8,
    ]
}

pub fn compile_sprite_atlas(
    input: &Path,
    output: &Path,
    options: SpriteCompileOptions,
    execute: bool,
) -> Result<SpriteCompileReport> {
    anyhow::ensure!(options.frame_count > 0, "frame count must be non-zero");
    anyhow::ensure!(
        options.cell_width > options.padding_px * 2 && options.cell_height > options.padding_px * 2,
        "padding must leave a non-empty cell"
    );
    anyhow::ensure!(
        options.baseline_y < options.cell_height,
        "baseline must be inside the cell"
    );
    if execute {
        anyhow::ensure!(
            !output.exists(),
            "refusing to overwrite {}",
            output.display()
        );
    }
    let source = decode_source(input)?;
    anyhow::ensure!(
        source.width >= options.frame_count && source.height > 0,
        "source is too small for the declared frame count"
    );
    let output_width = options
        .frame_count
        .checked_mul(options.cell_width)
        .context("output width overflow")?;
    let output_height = options.cell_height;
    let mut atlas = vec![0_u8; output_width as usize * output_height as usize * 4];
    let mut frames = Vec::with_capacity(options.frame_count as usize);

    for frame in 0..options.frame_count {
        let x0 = frame * source.width / options.frame_count;
        let x1 = (frame + 1) * source.width / options.frame_count;
        let [src_x, src_y, src_w, src_h] = alpha_bounds(&source, x0, x1)
            .with_context(|| format!("frame {frame} has no foreground after chroma extraction"))?;
        let max_w = options.cell_width - options.padding_px * 2;
        let max_h = options.baseline_y + 1 - options.padding_px;
        let scale = (max_w as f32 / src_w as f32).min(max_h as f32 / src_h as f32);
        let dst_w = ((src_w as f32 * scale).round() as u32).max(1);
        let dst_h = ((src_h as f32 * scale).round() as u32).max(1);
        let dst_x = frame * options.cell_width + (options.cell_width - dst_w) / 2;
        let dst_y = options.baseline_y + 1 - dst_h;

        for dy in 0..dst_h {
            for dx in 0..dst_w {
                let sx = src_x as f32 + (dx as f32 + 0.5) * src_w as f32 / dst_w as f32 - 0.5;
                let sy = src_y as f32 + (dy as f32 + 0.5) * src_h as f32 / dst_h as f32 - 0.5;
                let pixel = sample_bilinear(&source, sx, sy);
                let offset = (((dst_y + dy) * output_width + dst_x + dx) * 4) as usize;
                atlas[offset..offset + 4].copy_from_slice(&pixel);
            }
        }
        frames.push(SpriteCompileFrame {
            index: frame,
            source_bounds_xywh: [src_x, src_y, src_w, src_h],
            output_bounds_xywh: [dst_x - frame * options.cell_width, dst_y, dst_w, dst_h],
        });
    }

    if execute {
        if let Some(parent) = output.parent() {
            std::fs::create_dir_all(parent)
                .with_context(|| format!("create output directory {}", parent.display()))?;
        }
        let file = File::create(output).with_context(|| format!("create {}", output.display()))?;
        let mut encoder = png::Encoder::new(file, output_width, output_height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().context("write output PNG header")?;
        writer
            .write_image_data(&atlas)
            .context("write output PNG pixels")?;
        writer.finish().context("finish output PNG")?;
    }

    Ok(SpriteCompileReport {
        input: input.display().to_string(),
        output: output.display().to_string(),
        executed: execute,
        source_width: source.width,
        source_height: source.height,
        output_width,
        output_height,
        frame_count: options.frame_count,
        frames,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn compiles_magenta_strip_to_aligned_rgba_atlas() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let input = std::env::temp_dir().join(format!("ab-sprite-source-{nonce}.png"));
        let output = std::env::temp_dir().join(format!("ab-sprite-output-{nonce}.png"));
        let mut rgb = vec![0_u8; 8 * 4 * 3];
        for pixel in rgb.chunks_exact_mut(3) {
            pixel.copy_from_slice(&[255, 0, 255]);
        }
        for (x, color) in [(1_u32, [20, 80, 220]), (5_u32, [240, 210, 170])] {
            for y in 1..4_u32 {
                for dx in 0..2_u32 {
                    let offset = ((y * 8 + x + dx) * 3) as usize;
                    rgb[offset..offset + 3].copy_from_slice(&color);
                }
            }
        }
        let file = File::create(&input).unwrap();
        let mut encoder = png::Encoder::new(file, 8, 4);
        encoder.set_color(png::ColorType::Rgb);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().unwrap();
        writer.write_image_data(&rgb).unwrap();
        writer.finish().unwrap();

        let report = compile_sprite_atlas(
            &input,
            &output,
            SpriteCompileOptions {
                frame_count: 2,
                cell_width: 4,
                cell_height: 4,
                padding_px: 0,
                baseline_y: 3,
            },
            true,
        )
        .unwrap();
        let audit =
            crate::avatar_asset_audit::audit_sprite_asset(&output, 2, 1, 4, 4, Some(2), 4, 4, 0)
                .unwrap();
        std::fs::remove_file(input).unwrap();
        std::fs::remove_file(output).unwrap();
        assert!(report.executed);
        assert!(audit.accepted, "{:?}", audit.failures);
        assert_eq!(audit.baseline_drift_px, 0);
        assert!(audit.transparent_pixels > 0);
    }
}
