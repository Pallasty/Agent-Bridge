//! Bounded, read-only inspection of one local PNG or embedded GLB snapshot.
//! GLB checks are deliberately structural, not a glTF conformance or quality verdict.

use std::{
    fs::OpenOptions,
    io::{Cursor, Read},
    path::Path,
};

use anyhow::{anyhow, bail, ensure, Context, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

pub const REPORT_SCHEMA: &str = "agent_bridge.asset_inspection.v1";
pub const MAX_FILE_BYTES: u64 = 64 * 1024 * 1024;
const MAX_DECODED_BYTES: u64 = 64 * 1024 * 1024;
const MAX_GLB_JSON_BYTES: usize = 4 * 1024 * 1024;

/// Inspect a bounded byte snapshot without writing, executing, or fetching resources.
/// Expected digests accept exactly 64 ASCII hexadecimal digits, case-insensitively.
pub fn inspect_file(path: &Path, expected_sha256: Option<&str>) -> Result<Value> {
    if let Some(expected) = expected_sha256 {
        ensure!(
            expected.len() == 64 && expected.bytes().all(|byte| byte.is_ascii_hexdigit()),
            "expected_sha256 must contain exactly 64 hexadecimal digits"
        );
    }
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        // Nonblocking open prevents FIFO input from waiting before the fstat check.
        options.custom_flags(libc::O_NONBLOCK | libc::O_NOFOLLOW);
    }
    let file = options
        .open(path)
        .with_context(|| format!("open local asset {}", path.display()))?;
    let metadata = file.metadata().context("inspect opened asset file type")?;
    ensure!(
        metadata.is_file(),
        "asset input must be an ordinary regular file"
    );
    ensure!(
        metadata.len() <= MAX_FILE_BYTES,
        "asset exceeds the 64 MiB file limit"
    );
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    file.take(MAX_FILE_BYTES + 1)
        .read_to_end(&mut bytes)
        .context("read bounded asset snapshot")?;
    ensure!(
        bytes.len() as u64 <= MAX_FILE_BYTES,
        "asset exceeds the 64 MiB file limit"
    );
    let sha256 = format!("{:x}", Sha256::digest(&bytes));
    if let Some(expected) = expected_sha256 {
        ensure!(
            sha256.eq_ignore_ascii_case(expected),
            "SHA-256 mismatch: expected {}, observed {}",
            expected.to_ascii_lowercase(),
            sha256
        );
    }
    let (format, level, details) = if bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        ("png", "png_single_image_decoded", inspect_png(&bytes)?)
    } else if bytes.starts_with(b"glTF") {
        (
            "glb",
            "glb_embedded_structure_partial",
            inspect_glb(&bytes)?,
        )
    } else {
        bail!("unsupported asset magic; expected PNG or GLB v2");
    };
    Ok(json!({
        "schema": REPORT_SCHEMA, "path": path.to_string_lossy(), "bytes": bytes.len(),
        "sha256": sha256, "expected_sha256_matches": expected_sha256.map(|_| true),
        "format": format, "inspection_level": level, "details": details,
        "mesh_semantics_verified": false, "visual_quality_reviewed": false,
    }))
}

fn u32_at(bytes: &[u8], offset: usize, little_endian: bool) -> Result<u32> {
    let end = offset
        .checked_add(4)
        .ok_or_else(|| anyhow!("integer offset overflow"))?;
    let array: [u8; 4] = bytes
        .get(offset..end)
        .ok_or_else(|| anyhow!("truncated integer"))?
        .try_into()?;
    Ok(if little_endian {
        u32::from_le_bytes(array)
    } else {
        u32::from_be_bytes(array)
    })
}

fn inspect_png(bytes: &[u8]) -> Result<Value> {
    ensure!(
        bytes.len() >= 33 && &bytes[12..16] == b"IHDR" && u32_at(bytes, 8, false)? == 13,
        "PNG requires first IHDR chunk"
    );
    let width = u32_at(bytes, 16, false)?;
    let height = u32_at(bytes, 20, false)?;
    ensure!(width > 0 && height > 0, "PNG dimensions must be positive");
    // Upper bound before the decoder can allocate, including palette/tRNS expansion.
    let decoded_bound = u64::from(width)
        .checked_mul(u64::from(height))
        .and_then(|pixels| pixels.checked_mul(if bytes[24] == 16 { 8 } else { 4 }));
    ensure!(
        decoded_bound.is_some_and(|size| size <= MAX_DECODED_BYTES),
        "PNG decoded image exceeds the conservative 64 MiB RGBA limit"
    );
    let mut offset = 8usize;
    let mut ended = false;
    while offset < bytes.len() {
        let length = u32_at(bytes, offset, false)? as usize;
        let end = offset
            .checked_add(12)
            .and_then(|value| value.checked_add(length))
            .filter(|end| *end <= bytes.len())
            .ok_or_else(|| anyhow!("truncated PNG chunk before IEND"))?;
        let kind = &bytes[offset + 4..offset + 8];
        ensure!(
            !matches!(kind, b"acTL" | b"fcTL" | b"fdAT"),
            "APNG is unsupported; all-frame inspection is not implemented"
        );
        if kind == b"IEND" {
            ensure!(length == 0, "invalid PNG IEND length");
            ensure!(end == bytes.len(), "PNG has trailing bytes after IEND");
            ended = true;
            break;
        }
        offset = end;
    }
    ensure!(ended, "PNG is truncated or missing IEND");
    let mut options = png::DecodeOptions::default();
    options.set_ignore_checksums(false);
    let mut decoder = png::Decoder::new_with_options(Cursor::new(bytes), options);
    decoder.set_limits(png::Limits {
        bytes: MAX_DECODED_BYTES as usize,
    });
    decoder.set_transformations(png::Transformations::EXPAND);
    let mut reader = decoder.read_info().context("decode PNG header")?;
    let decoded_size = reader.output_buffer_size();
    ensure!(
        decoded_size as u64 <= MAX_DECODED_BYTES,
        "PNG decoded image exceeds 64 MiB"
    );
    let mut decoded = vec![0; decoded_size];
    let info = reader
        .next_frame(&mut decoded)
        .context("decode PNG pixels")?;
    reader.finish().context("decode PNG through IEND")?;
    let channels = info.color_type.samples();
    let has_alpha = matches!(
        info.color_type,
        png::ColorType::Rgba | png::ColorType::GrayscaleAlpha
    );
    let sample_bytes = if info.bit_depth == png::BitDepth::Sixteen {
        2
    } else {
        1
    };
    let mut transparent = 0u64;
    let mut partial = 0u64;
    for pixel in decoded[..info.buffer_size()].chunks_exact(channels * sample_bytes) {
        let alpha = if !has_alpha {
            65535
        } else if sample_bytes == 2 {
            u16::from_be_bytes([pixel[pixel.len() - 2], pixel[pixel.len() - 1]])
        } else {
            u16::from(pixel[pixel.len() - 1]) * 257
        };
        if alpha == 0 {
            transparent += 1;
        } else if alpha < 65535 {
            partial += 1;
        }
    }
    Ok(json!({
        "width": info.width, "height": info.height, "decoded_bytes": info.buffer_size(),
        "decoded_color_type": format!("{:?}", info.color_type), "decoded_bit_depth": format!("{:?}", info.bit_depth),
        "has_alpha": has_alpha, "fully_transparent_pixels": transparent,
        "partially_transparent_pixels": partial,
        "opaque_pixels": u64::from(width) * u64::from(height) - transparent - partial,
        "frame_count": 1, "iend_verified": true,
        "pixel_interpretation": "palette and tRNS expanded; 16-bit alpha retained; no visual-quality assessment",
    }))
}

fn array<'a>(value: &'a Value, name: &str) -> Result<&'a [Value]> {
    match value.get(name) {
        None => Ok(&[]),
        Some(Value::Array(values)) => Ok(values),
        _ => bail!("GLB {name} must be an array"),
    }
}

fn number(value: &Value, name: &str) -> Result<u64> {
    value
        .get(name)
        .and_then(Value::as_u64)
        .ok_or_else(|| anyhow!("GLB {name} must be an unsigned integer"))
}

fn optional_number(value: &Value, name: &str, default: u64) -> Result<u64> {
    if value.get(name).is_some() {
        number(value, name)
    } else {
        Ok(default)
    }
}

fn reference(value: &Value, limit: usize, label: &str) -> Result<usize> {
    let index = value
        .as_u64()
        .ok_or_else(|| anyhow!("GLB {label} reference must be an unsigned integer"))?;
    ensure!(
        index < limit as u64,
        "GLB {label} reference {index} is out of range"
    );
    Ok(index as usize)
}

fn inspect_glb(bytes: &[u8]) -> Result<Value> {
    ensure!(bytes.len() >= 20, "truncated GLB header length");
    ensure!(
        u32_at(bytes, 4, true)? == 2,
        "only GLB version 2 is supported"
    );
    ensure!(
        u32_at(bytes, 8, true)? as usize == bytes.len(),
        "GLB declared length does not match snapshot length"
    );
    let mut offset = 12usize;
    let mut json_bytes: Option<&[u8]> = None;
    let mut bin: Option<&[u8]> = None;
    while offset < bytes.len() {
        let length = u32_at(bytes, offset, true)? as usize;
        let kind = u32_at(bytes, offset + 4, true)?;
        ensure!(
            length % 4 == 0,
            "GLB chunk length must have 4-byte alignment"
        );
        let end = offset
            .checked_add(8)
            .and_then(|start| start.checked_add(length))
            .filter(|end| *end <= bytes.len())
            .ok_or_else(|| anyhow!("GLB chunk length exceeds snapshot"))?;
        if json_bytes.is_none() {
            ensure!(kind == 0x4e4f534a, "GLB first chunk must be JSON");
            ensure!(
                length <= MAX_GLB_JSON_BYTES,
                "GLB JSON chunk exceeds the 4 MiB metadata limit"
            );
            json_bytes = Some(&bytes[offset + 8..end]);
        } else {
            ensure!(
                kind == 0x004e4942 && bin.is_none(),
                "GLB subset permits one JSON then at most one BIN chunk"
            );
            bin = Some(&bytes[offset + 8..end]);
        }
        offset = end;
    }
    let document: Value =
        serde_json::from_slice(json_bytes.ok_or_else(|| anyhow!("GLB missing JSON chunk"))?)
            .context("parse GLB JSON")?;
    ensure!(
        document.is_object() && document["asset"]["version"] == "2.0",
        "GLB JSON asset.version must be 2.0"
    );
    if let Some(version) = document["asset"].get("minVersion") {
        ensure!(version == "2.0", "unsupported GLB asset.minVersion");
    }
    for unsupported in ["animations", "skins", "extensionsRequired"] {
        ensure!(
            array(&document, unsupported)?.is_empty(),
            "unsupported GLB {unsupported}; structural subset only"
        );
    }
    let buffers = array(&document, "buffers")?;
    let views = array(&document, "bufferViews")?;
    let accessors = array(&document, "accessors")?;
    let meshes = array(&document, "meshes")?;
    let nodes = array(&document, "nodes")?;
    let scenes = array(&document, "scenes")?;
    let images = array(&document, "images")?;
    for resource in buffers.iter().chain(images) {
        ensure!(resource.is_object(), "GLB resource must be an object");
        ensure!(
            resource.get("uri").is_none(),
            "external or data URI resources are unsupported and are never read"
        );
    }
    ensure!(
        buffers.len() <= 1,
        "GLB subset supports at most one embedded buffer"
    );
    let declared_buffer = if let Some(buffer) = buffers.first() {
        let declared = number(buffer, "byteLength")?;
        let binary = bin.ok_or_else(|| anyhow!("GLB embedded buffer requires BIN chunk"))?;
        let actual = binary.len() as u64;
        ensure!(
            declared > 0 && declared <= actual && actual - declared <= 3,
            "GLB BIN length does not match embedded buffer byteLength and padding"
        );
        ensure!(
            binary[declared as usize..].iter().all(|byte| *byte == 0),
            "GLB BIN padding must contain only zero bytes"
        );
        declared
    } else {
        ensure!(bin.is_none(), "GLB BIN chunk has no declared buffer");
        0
    };
    for view in views {
        reference(&view["buffer"], buffers.len(), "bufferView.buffer")?;
        let start = optional_number(view, "byteOffset", 0)?;
        let length = number(view, "byteLength")?;
        ensure!(
            length > 0
                && start
                    .checked_add(length)
                    .is_some_and(|end| end <= declared_buffer),
            "GLB bufferView range exceeds embedded buffer"
        );
        if view.get("byteStride").is_some() {
            let stride = number(view, "byteStride")?;
            ensure!(
                (4..=252).contains(&stride) && stride % 4 == 0,
                "invalid GLB bufferView byteStride"
            );
        }
    }
    for image in images {
        reference(&image["bufferView"], views.len(), "image.bufferView")?;
        ensure!(
            image["mimeType"].is_string(),
            "embedded GLB image requires mimeType"
        );
    }
    for accessor in accessors {
        ensure!(
            accessor.get("sparse").is_none(),
            "sparse GLB accessors are unsupported"
        );
        let view_index = reference(&accessor["bufferView"], views.len(), "accessor.bufferView")?;
        let view = &views[view_index];
        let component = number(accessor, "componentType")?;
        let component_bytes = match component {
            5120 | 5121 => 1,
            5122 | 5123 => 2,
            5125 | 5126 => 4,
            _ => bail!("invalid GLB accessor componentType"),
        };
        let components = match accessor["type"].as_str() {
            Some("SCALAR") => 1,
            Some("VEC2") => 2,
            Some("VEC3") => 3,
            Some("VEC4") => 4,
            _ => bail!("unsupported GLB accessor type; only SCALAR/VEC2/VEC3/VEC4 are inspected"),
        };
        let element = component_bytes * components;
        let count = number(accessor, "count")?;
        let start = optional_number(accessor, "byteOffset", 0)?;
        let stride = optional_number(view, "byteStride", element)?;
        ensure!(
            count > 0
                && stride >= element
                && stride % component_bytes == 0
                && start % component_bytes == 0,
            "invalid GLB accessor count, stride, or alignment"
        );
        let absolute = optional_number(view, "byteOffset", 0)?.checked_add(start);
        ensure!(
            absolute.is_some_and(|value| value % component_bytes == 0),
            "invalid GLB accessor absolute alignment"
        );
        let end = (count - 1)
            .checked_mul(stride)
            .and_then(|span| span.checked_add(element))
            .and_then(|span| start.checked_add(span));
        ensure!(
            end.is_some_and(|value| value <= number(view, "byteLength").unwrap_or(0)),
            "GLB accessor span exceeds bufferView range"
        );
    }
    let mut primitive_count = 0usize;
    let mut declared_position_count = 0u64;
    for mesh in meshes {
        let primitives = array(mesh, "primitives")?;
        ensure!(!primitives.is_empty(), "GLB mesh must declare primitives");
        for primitive in primitives {
            ensure!(
                array(primitive, "targets")?.is_empty(),
                "GLB morph targets are unsupported"
            );
            ensure!(
                optional_number(primitive, "mode", 4)? <= 6,
                "invalid GLB primitive mode"
            );
            let attributes = primitive["attributes"]
                .as_object()
                .ok_or_else(|| anyhow!("GLB primitive attributes must be an object"))?;
            let position = reference(
                attributes.get("POSITION").unwrap_or(&Value::Null),
                accessors.len(),
                "POSITION accessor",
            )?;
            ensure!(
                accessors[position]["type"] == "VEC3"
                    && accessors[position]["componentType"] == 5126,
                "GLB POSITION accessor requires float VEC3"
            );
            let vertices = number(&accessors[position], "count")?;
            for attribute in attributes.values() {
                let index = reference(attribute, accessors.len(), "attribute accessor")?;
                ensure!(
                    number(&accessors[index], "count")? == vertices,
                    "GLB attribute accessor counts differ"
                );
            }
            if let Some(indices) = primitive.get("indices") {
                let index = reference(indices, accessors.len(), "indices accessor")?;
                ensure!(
                    accessors[index]["type"] == "SCALAR"
                        && matches!(
                            number(&accessors[index], "componentType")?,
                            5121 | 5123 | 5125
                        ),
                    "GLB indices accessor must be unsigned SCALAR"
                );
            }
            if let Some(material) = primitive.get("material") {
                reference(
                    material,
                    array(&document, "materials")?.len(),
                    "primitive.material",
                )?;
            }
            declared_position_count = declared_position_count
                .checked_add(vertices)
                .ok_or_else(|| anyhow!("declared POSITION count overflow"))?;
            primitive_count += 1;
        }
    }
    for node in nodes {
        ensure!(node.is_object(), "GLB node must be an object");
        if let Some(mesh) = node.get("mesh") {
            reference(mesh, meshes.len(), "node.mesh")?;
        }
        for child in array(node, "children")? {
            reference(child, nodes.len(), "node.children")?;
        }
    }
    for scene in scenes {
        ensure!(scene.is_object(), "GLB scene must be an object");
        for node in array(scene, "nodes")? {
            reference(node, nodes.len(), "scene.nodes")?;
        }
    }
    if let Some(scene) = document.get("scene") {
        reference(scene, scenes.len(), "scene")?;
    }
    Ok(json!({
        "container_version": 2, "buffer_count": buffers.len(), "buffer_view_count": views.len(),
        "accessor_count": accessors.len(), "mesh_count": meshes.len(), "primitive_count": primitive_count,
        "node_count": nodes.len(), "scene_count": scenes.len(), "image_count": images.len(),
        "declared_position_count_summed_per_primitive": declared_position_count,
        "embedded_buffer_bytes": declared_buffer, "external_resources_read": false,
        "json_chunk_limit_bytes": MAX_GLB_JSON_BYTES,
        "checks": ["header/chunk length and order", "embedded buffer ranges", "basic accessor spans/alignment", "mesh/node/scene references"],
        "not_verified": ["full glTF schema/conformance", "index values and geometry topology", "vertex numeric values", "node graph/transforms", "material/texture/image semantics", "optional extension semantics", "visual quality"],
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};
    use sha2::{Digest, Sha256};
    use std::io::Write;

    fn inspect(bytes: &[u8], expected: Option<&str>) -> anyhow::Result<Value> {
        let mut file = tempfile::Builder::new().suffix(".unknown").tempfile()?;
        file.write_all(bytes)?;
        inspect_file(file.path(), expected)
    }

    fn png_bytes(animated: bool) -> Vec<u8> {
        let mut bytes = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut bytes, 3, 1);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            if animated {
                encoder.set_animated(1, 0).unwrap();
            }
            let mut writer = encoder.write_header().unwrap();
            writer
                .write_image_data(&[0, 0, 0, 0, 100, 100, 100, 128, 255, 255, 255, 255])
                .unwrap();
            writer.finish().unwrap();
        }
        bytes
    }

    fn glb_json() -> Value {
        json!({
            "asset": {"version":"2.0"}, "scene":0,
            "scenes":[{"nodes":[0]}], "nodes":[{"mesh":0}],
            "buffers":[{"byteLength":42}],
            "bufferViews":[{"buffer":0,"byteLength":36}, {"buffer":0,"byteOffset":36,"byteLength":6}],
            "accessors":[
                {"bufferView":0,"componentType":5126,"count":3,"type":"VEC3"},
                {"bufferView":1,"componentType":5123,"count":3,"type":"SCALAR"}
            ],
            "meshes":[{"primitives":[{"attributes":{"POSITION":0},"indices":1}]}]
        })
    }

    fn glb_bytes(document: &Value) -> Vec<u8> {
        let mut json = serde_json::to_vec(document).unwrap();
        while json.len() % 4 != 0 {
            json.push(b' ');
        }
        let mut bytes = b"glTF".to_vec();
        bytes.extend(2u32.to_le_bytes());
        bytes.extend((12u32 + 8 + json.len() as u32 + 8 + 44).to_le_bytes());
        bytes.extend((json.len() as u32).to_le_bytes());
        bytes.extend(0x4e4f534au32.to_le_bytes());
        bytes.extend(json);
        bytes.extend(44u32.to_le_bytes());
        bytes.extend(0x004e4942u32.to_le_bytes());
        bytes.extend([0; 44]);
        bytes
    }

    #[test]
    fn test_png_snapshot_reports_dimensions_alpha_and_hash_by_magic() {
        let bytes = png_bytes(false);
        let result = inspect(&bytes, None).unwrap();
        assert_eq!(result["schema"], REPORT_SCHEMA);
        assert_eq!(result["bytes"], bytes.len());
        assert_eq!(result["sha256"], format!("{:x}", Sha256::digest(&bytes)));
        assert_eq!(result["format"], "png");
        assert_eq!(result["details"]["width"], 3);
        assert_eq!(result["details"]["height"], 1);
        assert_eq!(result["details"]["fully_transparent_pixels"], 1);
        assert_eq!(result["details"]["partially_transparent_pixels"], 1);
        assert_eq!(result["details"]["opaque_pixels"], 1);
        assert!(result["expected_sha256_matches"].is_null());
        assert_eq!(result["mesh_semantics_verified"], false);
        assert_eq!(result["visual_quality_reviewed"], false);
    }

    #[test]
    fn test_expected_hash_accepts_uppercase_and_rejects_mismatch_with_evidence() {
        let bytes = png_bytes(false);
        let digest = format!("{:x}", Sha256::digest(&bytes));
        assert_eq!(
            inspect(&bytes, Some(&digest.to_uppercase())).unwrap()["expected_sha256_matches"],
            true
        );
        let expected = "0".repeat(64);
        let message = inspect(&bytes, Some(&expected)).unwrap_err().to_string();
        assert!(message.contains(&digest) && message.contains(&expected));
    }

    #[test]
    fn test_malformed_hash_is_rejected_before_file_open() {
        let error =
            inspect_file(std::path::Path::new("/missing/asset.png"), Some("abc")).unwrap_err();
        assert!(error.to_string().contains("64 hexadecimal"));
    }

    #[test]
    fn test_png_truncation_and_trailing_bytes_are_rejected() {
        let mut bytes = png_bytes(false);
        bytes.truncate(bytes.len() - 12);
        assert!(inspect(&bytes, None)
            .unwrap_err()
            .to_string()
            .contains("IEND"));
        let mut trailing = png_bytes(false);
        trailing.extend(b"not-png");
        assert!(inspect(&trailing, None)
            .unwrap_err()
            .to_string()
            .contains("trailing"));
    }

    #[test]
    fn test_png_corruption_and_animation_are_rejected() {
        let mut bytes = png_bytes(false);
        let idat = bytes.windows(4).position(|value| value == b"IDAT").unwrap();
        bytes[idat + 4] ^= 0xff;
        assert!(inspect(&bytes, None).is_err());
        assert!(inspect(&png_bytes(true), None)
            .unwrap_err()
            .to_string()
            .contains("APNG"));
    }

    #[test]
    fn test_png_huge_decoded_dimensions_are_rejected_before_allocation() {
        let mut bytes = png_bytes(false);
        bytes[16..20].copy_from_slice(&100_000u32.to_be_bytes());
        bytes[20..24].copy_from_slice(&100_000u32.to_be_bytes());
        assert!(inspect(&bytes, None)
            .unwrap_err()
            .to_string()
            .contains("decoded"));
    }

    #[test]
    fn test_glb_embedded_structure_has_explicit_partial_result() {
        let result = inspect(&glb_bytes(&glb_json()), None).unwrap();
        assert_eq!(result["format"], "glb");
        assert_eq!(result["inspection_level"], "glb_embedded_structure_partial");
        assert_eq!(result["details"]["mesh_count"], 1);
        assert_eq!(result["details"]["accessor_count"], 2);
        assert_eq!(result["mesh_semantics_verified"], false);
        assert_eq!(result["details"]["external_resources_read"], false);
    }

    #[test]
    fn test_glb_header_length_and_chunk_order_are_rejected() {
        let mut bytes = glb_bytes(&glb_json());
        bytes[8..12].copy_from_slice(&12u32.to_le_bytes());
        assert!(inspect(&bytes, None)
            .unwrap_err()
            .to_string()
            .contains("length"));
        let mut bytes = glb_bytes(&glb_json());
        bytes[16..20].copy_from_slice(&0x004e4942u32.to_le_bytes());
        assert!(inspect(&bytes, None)
            .unwrap_err()
            .to_string()
            .contains("JSON"));
    }

    #[test]
    fn test_glb_external_uri_and_unsupported_accessors_are_rejected() {
        let mut document = glb_json();
        document["buffers"][0]["uri"] = json!("file:///must-not-be-read.bin");
        assert!(inspect(&glb_bytes(&document), None)
            .unwrap_err()
            .to_string()
            .contains("URI"));
        let mut document = glb_json();
        document["accessors"][0]["sparse"] = json!({});
        assert!(inspect(&glb_bytes(&document), None)
            .unwrap_err()
            .to_string()
            .contains("sparse"));
    }

    #[test]
    fn test_glb_accessor_span_and_references_are_checked() {
        let mut document = glb_json();
        document["accessors"][0]["count"] = json!(4);
        assert!(inspect(&glb_bytes(&document), None)
            .unwrap_err()
            .to_string()
            .contains("accessor"));
        let mut document = glb_json();
        document["meshes"][0]["primitives"][0]["attributes"]["POSITION"] = json!(9);
        assert!(inspect(&glb_bytes(&document), None)
            .unwrap_err()
            .to_string()
            .contains("reference"));
        let mut document = glb_json();
        document["scenes"][0]["nodes"] = json!([9]);
        assert!(inspect(&glb_bytes(&document), None)
            .unwrap_err()
            .to_string()
            .contains("reference"));
    }

    #[test]
    fn test_unknown_format_nonfile_and_oversize_are_rejected() {
        assert!(inspect(b"not an image", None)
            .unwrap_err()
            .to_string()
            .contains("unsupported"));
        let directory = tempfile::tempdir().unwrap();
        assert!(inspect_file(directory.path(), None)
            .unwrap_err()
            .to_string()
            .contains("regular"));
        let file = tempfile::NamedTempFile::new().unwrap();
        file.as_file().set_len(MAX_FILE_BYTES + 1).unwrap();
        assert!(inspect_file(file.path(), None)
            .unwrap_err()
            .to_string()
            .contains("64 MiB"));
    }

    #[cfg(unix)]
    #[test]
    fn test_fifo_is_rejected_without_waiting_for_writer() {
        use std::os::unix::ffi::OsStrExt;
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("pipe.png");
        let name = std::ffi::CString::new(path.as_os_str().as_bytes()).unwrap();
        // The CString is live and NUL-terminated for this immediate syscall.
        assert_eq!(unsafe { libc::mkfifo(name.as_ptr(), 0o600) }, 0);
        let start = std::time::Instant::now();
        assert!(inspect_file(&path, None)
            .unwrap_err()
            .to_string()
            .contains("regular"));
        assert!(start.elapsed() < std::time::Duration::from_secs(2));
    }
    #[test]
    fn test_glb_binary_padding_must_be_zero() {
        let mut bytes = glb_bytes(&glb_json());
        *bytes.last_mut().unwrap() = 1;
        assert!(inspect(&bytes, None)
            .unwrap_err()
            .to_string()
            .contains("padding"));
    }

    #[test]
    fn test_png_sixteen_bit_alpha_preserves_small_nonzero_values() {
        let mut bytes = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut bytes, 3, 1);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Sixteen);
            let mut writer = encoder.write_header().unwrap();
            let mut pixels = Vec::new();
            for alpha in [0u16, 1, 65535] {
                pixels.extend([0u8; 6]);
                pixels.extend(alpha.to_be_bytes());
            }
            writer.write_image_data(&pixels).unwrap();
            writer.finish().unwrap();
        }
        let result = inspect(&bytes, None).unwrap();
        assert_eq!(result["details"]["fully_transparent_pixels"], 1);
        assert_eq!(result["details"]["partially_transparent_pixels"], 1);
        assert_eq!(result["details"]["opaque_pixels"], 1);
        assert_eq!(result["details"]["decoded_bit_depth"], "Sixteen");
    }

    #[test]
    fn test_png_palette_transparency_is_expanded_before_counting() {
        let mut bytes = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut bytes, 3, 1);
            encoder.set_color(png::ColorType::Indexed);
            encoder.set_depth(png::BitDepth::Eight);
            encoder.set_palette(vec![0, 0, 0, 100, 100, 100, 255, 255, 255]);
            encoder.set_trns(vec![0, 128, 255]);
            let mut writer = encoder.write_header().unwrap();
            writer.write_image_data(&[0, 1, 2]).unwrap();
            writer.finish().unwrap();
        }
        let result = inspect(&bytes, None).unwrap();
        assert_eq!(result["details"]["fully_transparent_pixels"], 1);
        assert_eq!(result["details"]["partially_transparent_pixels"], 1);
        assert_eq!(result["details"]["opaque_pixels"], 1);
        assert_eq!(result["details"]["has_alpha"], true);
    }

    #[test]
    fn test_glb_json_chunk_has_separate_preparse_limit() {
        let mut document = glb_json();
        document["extras"] = json!("x".repeat(4 * 1024 * 1024));
        assert!(inspect(&glb_bytes(&document), None)
            .unwrap_err()
            .to_string()
            .contains("JSON chunk"));
    }
}
