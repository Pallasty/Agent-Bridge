//! Read-only Qwen3-TTS SafeTensors inventory and static quantization diagnostics.
//!
//! This crate deliberately has no model writer and no runtime integration. It
//! maps source files read-only, validates their SafeTensors layout, samples
//! tensor values deterministically, and emits a stable JSON report.

use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::Path;

use anyhow::{anyhow, bail, Context, Result};
use half::f16;
use memmap2::MmapOptions;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

pub const REPORT_SCHEMA: &str = "agent_bridge.qwen3_tts.quant_static_report.v0";
const MAX_HEADER_BYTES: usize = 128 * 1024 * 1024;

#[derive(Debug, Clone)]
pub struct AnalyzeOptions {
    pub sample_size: usize,
    pub min_elements: u64,
    pub entropy_bins: Vec<usize>,
    pub group_sizes: Vec<usize>,
    pub include_sha256: bool,
}

impl Default for AnalyzeOptions {
    fn default() -> Self {
        Self {
            sample_size: 8192,
            min_elements: 4096,
            entropy_bins: vec![64, 256, 1024],
            group_sizes: vec![32, 64, 128, 256],
            include_sha256: false,
        }
    }
}

impl AnalyzeOptions {
    fn validate(&self) -> Result<()> {
        if self.sample_size < 128 {
            bail!("sample_size must be at least 128");
        }
        if self.entropy_bins.is_empty()
            || self
                .entropy_bins
                .iter()
                .any(|&bins| !(2..=65_536).contains(&bins))
        {
            bail!("entropy_bins must contain values in 2..=65536");
        }
        if self.group_sizes.is_empty()
            || self
                .group_sizes
                .iter()
                .any(|&size| size == 0 || size > 65_536)
        {
            bail!("group_sizes must contain values in 1..=65536");
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct StaticReport {
    pub schema: String,
    pub model_snapshot_name: String,
    pub sample_strategy: String,
    pub sample_size: usize,
    pub min_elements: u64,
    pub entropy_bins: Vec<usize>,
    pub group_sizes: Vec<usize>,
    pub files: Vec<FileReport>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FileReport {
    pub relative_path: String,
    pub partition: String,
    pub bytes: u64,
    pub sha256: Option<String>,
    pub tensor_count: usize,
    pub dtype_counts: BTreeMap<String, usize>,
    pub tensors: Vec<TensorReport>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TensorReport {
    pub name: String,
    pub family: String,
    pub dtype: String,
    pub shape: Vec<u64>,
    pub element_count: u64,
    pub data_offsets: [u64; 2],
    pub evidence_level: String,
    pub diagnostics: Option<TensorDiagnostics>,
    pub skipped_reason: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct TensorDiagnostics {
    pub sampled_values: usize,
    pub finite_values: usize,
    pub min: f64,
    pub max: f64,
    pub mean: f64,
    pub rms: f64,
    pub standard_deviation: f64,
    pub kurtosis: f64,
    pub zero_ratio: f64,
    pub median_abs: f64,
    pub outlier_ratio_6x_median_abs: f64,
    pub normalized_entropy: BTreeMap<String, f64>,
    pub robust_normalized_entropy: BTreeMap<String, f64>,
    pub per_tensor_q8_nrmse: f64,
    pub per_tensor_q4_nrmse: f64,
    pub groupwise_q8_nrmse: BTreeMap<String, f64>,
    pub groupwise_q4_nrmse: BTreeMap<String, f64>,
}

#[derive(Debug)]
struct TensorMeta {
    name: String,
    dtype: String,
    shape: Vec<u64>,
    offsets: [u64; 2],
    elements: u64,
}

pub fn analyze_model_dir(model_dir: &Path, options: &AnalyzeOptions) -> Result<StaticReport> {
    options.validate()?;
    let metadata = std::fs::metadata(model_dir)
        .with_context(|| format!("model directory is unavailable: {}", model_dir.display()))?;
    if !metadata.is_dir() {
        bail!("model_dir is not a directory: {}", model_dir.display());
    }

    let known_files = [
        ("model.safetensors", "talker"),
        (
            "speech_tokenizer/model.safetensors",
            "speech_tokenizer_codec",
        ),
    ];
    let mut files = Vec::new();
    for (relative, partition) in known_files {
        let path = model_dir.join(relative);
        if !path.is_file() {
            bail!("required Qwen3-TTS asset is missing: {}", path.display());
        }
        files.push(analyze_file(&path, relative, partition, options)?);
    }

    Ok(StaticReport {
        schema: REPORT_SCHEMA.to_string(),
        model_snapshot_name: model_dir
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("unknown")
            .to_string(),
        sample_strategy: "deterministic_even_spacing_plus_real_contiguous_groups".to_string(),
        sample_size: options.sample_size,
        min_elements: options.min_elements,
        entropy_bins: sorted_unique(&options.entropy_bins),
        group_sizes: sorted_unique(&options.group_sizes),
        files,
    })
}

pub fn write_report(report: &StaticReport, output: Option<&Path>, model_dir: &Path) -> Result<()> {
    match output {
        None => {
            let stdout = io::stdout();
            let mut writer = BufWriter::new(stdout.lock());
            serde_json::to_writer_pretty(&mut writer, report)?;
            writer.write_all(b"\n")?;
            writer.flush()?;
        }
        Some(path) => {
            ensure_output_outside_model(path, model_dir)?;
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).with_context(|| {
                    format!("failed to create report directory: {}", parent.display())
                })?;
            }
            let file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(path)
                .with_context(|| {
                    format!(
                        "refusing to overwrite or create report at unavailable path: {}",
                        path.display()
                    )
                })?;
            let mut writer = BufWriter::new(file);
            serde_json::to_writer_pretty(&mut writer, report)?;
            writer.write_all(b"\n")?;
            writer.flush()?;
        }
    }
    Ok(())
}

fn ensure_output_outside_model(output: &Path, model_dir: &Path) -> Result<()> {
    let model = model_dir
        .canonicalize()
        .with_context(|| format!("failed to resolve model_dir: {}", model_dir.display()))?;
    let absolute_output = if output.is_absolute() {
        output.to_path_buf()
    } else {
        std::env::current_dir()?.join(output)
    };
    let output_parent = absolute_output
        .parent()
        .ok_or_else(|| anyhow!("output path has no parent: {}", output.display()))?;
    let resolved_parent = if output_parent.exists() {
        output_parent.canonicalize()?
    } else {
        let mut cursor = output_parent;
        while !cursor.exists() {
            cursor = cursor.parent().ok_or_else(|| {
                anyhow!("output path has no existing ancestor: {}", output.display())
            })?;
        }
        cursor.canonicalize()?
    };
    if resolved_parent.starts_with(&model) {
        bail!(
            "report output must be outside the model directory: {}",
            output.display()
        );
    }
    Ok(())
}

fn analyze_file(
    path: &Path,
    relative_path: &str,
    partition: &str,
    options: &AnalyzeOptions,
) -> Result<FileReport> {
    let file = File::open(path)
        .with_context(|| format!("failed to open SafeTensors file: {}", path.display()))?;
    let file_len = file.metadata()?.len();
    // SAFETY: the file is opened read-only and the returned map is never exposed
    // mutably. All offsets are validated before slicing.
    let mmap = unsafe { MmapOptions::new().map(&file)? };
    let (data_base, mut tensors) = parse_header(&mmap, path)?;
    validate_tensor_layout(&tensors, file_len, data_base as u64, path)?;
    tensors.sort_by(|a, b| a.name.cmp(&b.name));

    let mut dtype_counts = BTreeMap::new();
    let mut tensor_reports = Vec::with_capacity(tensors.len());
    for tensor in tensors {
        *dtype_counts.entry(tensor.dtype.clone()).or_insert(0) += 1;
        tensor_reports.push(analyze_tensor(&mmap, data_base, &tensor, options)?);
    }

    Ok(FileReport {
        relative_path: relative_path.to_string(),
        partition: partition.to_string(),
        bytes: file_len,
        sha256: if options.include_sha256 {
            Some(sha256_file(path)?)
        } else {
            None
        },
        tensor_count: tensor_reports.len(),
        dtype_counts,
        tensors: tensor_reports,
    })
}

fn parse_header(mmap: &[u8], path: &Path) -> Result<(usize, Vec<TensorMeta>)> {
    if mmap.len() < 8 {
        bail!(
            "SafeTensors file is shorter than its length prefix: {}",
            path.display()
        );
    }
    let header_len = u64::from_le_bytes(mmap[0..8].try_into().expect("8-byte prefix")) as usize;
    if header_len == 0 || header_len > MAX_HEADER_BYTES {
        bail!(
            "invalid SafeTensors header length {} in {}",
            header_len,
            path.display()
        );
    }
    let data_base = 8usize
        .checked_add(header_len)
        .ok_or_else(|| anyhow!("SafeTensors header length overflow"))?;
    if data_base > mmap.len() {
        bail!("SafeTensors header exceeds file length: {}", path.display());
    }
    let value: Value = serde_json::from_slice(&mmap[8..data_base])
        .with_context(|| format!("invalid SafeTensors JSON header: {}", path.display()))?;
    let object = value
        .as_object()
        .ok_or_else(|| anyhow!("SafeTensors header must be a JSON object"))?;
    let mut tensors = Vec::new();
    for (name, meta) in object {
        if name == "__metadata__" {
            continue;
        }
        let meta = meta
            .as_object()
            .ok_or_else(|| anyhow!("tensor metadata must be an object: {name}"))?;
        let dtype = meta
            .get("dtype")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("tensor dtype is missing: {name}"))?
            .to_string();
        let shape = meta
            .get("shape")
            .and_then(Value::as_array)
            .ok_or_else(|| anyhow!("tensor shape is missing: {name}"))?
            .iter()
            .map(|value| {
                value
                    .as_u64()
                    .ok_or_else(|| anyhow!("tensor shape contains a non-u64 value: {name}"))
            })
            .collect::<Result<Vec<_>>>()?;
        let offsets_vec = meta
            .get("data_offsets")
            .and_then(Value::as_array)
            .ok_or_else(|| anyhow!("tensor data_offsets are missing: {name}"))?;
        if offsets_vec.len() != 2 {
            bail!("tensor data_offsets must contain two values: {name}");
        }
        let offsets = [
            offsets_vec[0]
                .as_u64()
                .ok_or_else(|| anyhow!("invalid tensor start offset: {name}"))?,
            offsets_vec[1]
                .as_u64()
                .ok_or_else(|| anyhow!("invalid tensor end offset: {name}"))?,
        ];
        let elements = shape.iter().try_fold(1u64, |acc, &dim| {
            acc.checked_mul(dim)
                .ok_or_else(|| anyhow!("tensor element count overflow: {name}"))
        })?;
        tensors.push(TensorMeta {
            name: name.clone(),
            dtype,
            shape,
            offsets,
            elements,
        });
    }
    if tensors.is_empty() {
        bail!("SafeTensors header contains no tensors: {}", path.display());
    }
    Ok((data_base, tensors))
}

fn validate_tensor_layout(
    tensors: &[TensorMeta],
    file_len: u64,
    data_base: u64,
    path: &Path,
) -> Result<()> {
    let data_len = file_len
        .checked_sub(data_base)
        .ok_or_else(|| anyhow!("SafeTensors data base exceeds file length"))?;
    let mut spans = Vec::with_capacity(tensors.len());
    for tensor in tensors {
        let [start, end] = tensor.offsets;
        if start > end || end > data_len {
            bail!(
                "tensor {} has out-of-range offsets {:?} in {}",
                tensor.name,
                tensor.offsets,
                path.display()
            );
        }
        if let Some(bytes_per_element) = dtype_size(&tensor.dtype) {
            let expected = tensor
                .elements
                .checked_mul(bytes_per_element as u64)
                .ok_or_else(|| anyhow!("tensor byte size overflow: {}", tensor.name))?;
            if end - start != expected {
                bail!(
                    "tensor {} byte length {} does not match shape/dtype expectation {}",
                    tensor.name,
                    end - start,
                    expected
                );
            }
        }
        spans.push((start, end, tensor.name.as_str()));
    }
    spans.sort_by_key(|span| span.0);
    for pair in spans.windows(2) {
        if pair[0].1 > pair[1].0 {
            bail!(
                "tensor byte ranges overlap: {} and {}",
                pair[0].2,
                pair[1].2
            );
        }
    }
    Ok(())
}

fn analyze_tensor(
    mmap: &[u8],
    data_base: usize,
    tensor: &TensorMeta,
    options: &AnalyzeOptions,
) -> Result<TensorReport> {
    let family = classify_family(&tensor.name);
    let mut report = TensorReport {
        name: tensor.name.clone(),
        family,
        dtype: tensor.dtype.clone(),
        shape: tensor.shape.clone(),
        element_count: tensor.elements,
        data_offsets: tensor.offsets,
        evidence_level: "inventory_only".to_string(),
        diagnostics: None,
        skipped_reason: None,
    };

    if dtype_size(&tensor.dtype).is_none() {
        report.skipped_reason = Some(format!("unsupported dtype {}", tensor.dtype));
        return Ok(report);
    }
    if tensor.shape.len() < 2 {
        report.skipped_reason = Some("rank below 2".to_string());
        return Ok(report);
    }
    if tensor.elements < options.min_elements {
        report.skipped_reason = Some(format!(
            "element count below min_elements {}",
            options.min_elements
        ));
        return Ok(report);
    }

    let start = data_base
        .checked_add(tensor.offsets[0] as usize)
        .ok_or_else(|| anyhow!("tensor start offset overflow: {}", tensor.name))?;
    let end = data_base
        .checked_add(tensor.offsets[1] as usize)
        .ok_or_else(|| anyhow!("tensor end offset overflow: {}", tensor.name))?;
    let bytes = mmap
        .get(start..end)
        .ok_or_else(|| anyhow!("validated tensor slice became unavailable: {}", tensor.name))?;
    let values = evenly_spaced_values(
        bytes,
        &tensor.dtype,
        tensor.elements as usize,
        options.sample_size,
    )?;
    let finite = values
        .iter()
        .copied()
        .filter(|value| value.is_finite())
        .collect::<Vec<_>>();
    if finite.len() < 2 {
        report.skipped_reason = Some("fewer than two finite sampled values".to_string());
        return Ok(report);
    }

    let mut entropy_bins = sorted_unique(&options.entropy_bins);
    entropy_bins.retain(|&bins| bins >= 2);
    let mut normalized_entropy = BTreeMap::new();
    let mut robust_normalized_entropy = BTreeMap::new();
    let robust = clipped_values(&finite, 0.005, 0.995);
    for bins in entropy_bins {
        normalized_entropy.insert(bins.to_string(), normalized_entropy_score(&finite, bins));
        robust_normalized_entropy.insert(bins.to_string(), normalized_entropy_score(&robust, bins));
    }

    let mut groupwise_q8_nrmse = BTreeMap::new();
    let mut groupwise_q4_nrmse = BTreeMap::new();
    for group_size in sorted_unique(&options.group_sizes) {
        groupwise_q8_nrmse.insert(
            group_size.to_string(),
            sampled_group_nrmse(
                bytes,
                &tensor.dtype,
                tensor.elements as usize,
                group_size,
                options.sample_size,
                8,
            )?,
        );
        groupwise_q4_nrmse.insert(
            group_size.to_string(),
            sampled_group_nrmse(
                bytes,
                &tensor.dtype,
                tensor.elements as usize,
                group_size,
                options.sample_size,
                4,
            )?,
        );
    }

    let basic = basic_stats(&finite);
    report.evidence_level = "static_distribution".to_string();
    report.diagnostics = Some(TensorDiagnostics {
        sampled_values: values.len(),
        finite_values: finite.len(),
        min: basic.min,
        max: basic.max,
        mean: basic.mean,
        rms: basic.rms,
        standard_deviation: basic.standard_deviation,
        kurtosis: basic.kurtosis,
        zero_ratio: basic.zero_ratio,
        median_abs: basic.median_abs,
        outlier_ratio_6x_median_abs: basic.outlier_ratio,
        normalized_entropy,
        robust_normalized_entropy,
        per_tensor_q8_nrmse: symmetric_nrmse(&finite, 8),
        per_tensor_q4_nrmse: symmetric_nrmse(&finite, 4),
        groupwise_q8_nrmse,
        groupwise_q4_nrmse,
    });
    Ok(report)
}

#[derive(Debug)]
struct BasicStats {
    min: f64,
    max: f64,
    mean: f64,
    rms: f64,
    standard_deviation: f64,
    kurtosis: f64,
    zero_ratio: f64,
    median_abs: f64,
    outlier_ratio: f64,
}

fn basic_stats(values: &[f32]) -> BasicStats {
    let count = values.len() as f64;
    let min = values.iter().copied().fold(f32::INFINITY, f32::min) as f64;
    let max = values.iter().copied().fold(f32::NEG_INFINITY, f32::max) as f64;
    let mean = values.iter().map(|&value| value as f64).sum::<f64>() / count;
    let second = values
        .iter()
        .map(|&value| {
            let value = value as f64;
            value * value
        })
        .sum::<f64>()
        / count;
    let variance = values
        .iter()
        .map(|&value| {
            let delta = value as f64 - mean;
            delta * delta
        })
        .sum::<f64>()
        / count;
    let fourth = values
        .iter()
        .map(|&value| {
            let delta = value as f64 - mean;
            delta.powi(4)
        })
        .sum::<f64>()
        / count;
    let mut absolute = values.iter().map(|value| value.abs()).collect::<Vec<_>>();
    absolute.sort_by(f32::total_cmp);
    let median_abs = percentile_sorted(&absolute, 0.5) as f64;
    let threshold = (median_abs * 6.0).max(f32::EPSILON as f64);
    let outlier_ratio = values
        .iter()
        .filter(|value| value.abs() as f64 > threshold)
        .count() as f64
        / count;
    BasicStats {
        min,
        max,
        mean,
        rms: second.sqrt(),
        standard_deviation: variance.sqrt(),
        kurtosis: if variance > 0.0 {
            fourth / variance.powi(2)
        } else {
            0.0
        },
        zero_ratio: values.iter().filter(|&&value| value == 0.0).count() as f64 / count,
        median_abs,
        outlier_ratio,
    }
}

fn evenly_spaced_values(
    bytes: &[u8],
    dtype: &str,
    elements: usize,
    sample_size: usize,
) -> Result<Vec<f32>> {
    let take = elements.min(sample_size);
    if take == 0 {
        return Ok(Vec::new());
    }
    let mut values = Vec::with_capacity(take);
    if take == 1 {
        values.push(decode_value(bytes, dtype, 0)?);
        return Ok(values);
    }
    for sample in 0..take {
        let index = sample
            .checked_mul(elements - 1)
            .ok_or_else(|| anyhow!("sample index overflow"))?
            / (take - 1);
        values.push(decode_value(bytes, dtype, index)?);
    }
    Ok(values)
}

fn sampled_group_nrmse(
    bytes: &[u8],
    dtype: &str,
    elements: usize,
    group_size: usize,
    sample_budget: usize,
    bits: u8,
) -> Result<f64> {
    if elements == 0 {
        return Ok(0.0);
    }
    let total_groups = elements.div_ceil(group_size);
    let groups_to_sample = total_groups.min((sample_budget / group_size).max(1));
    let mut error_squared = 0.0f64;
    let mut source_squared = 0.0f64;
    for sample in 0..groups_to_sample {
        let group_index = if groups_to_sample == 1 {
            0
        } else {
            sample * (total_groups - 1) / (groups_to_sample - 1)
        };
        let start = group_index * group_size;
        let end = (start + group_size).min(elements);
        let mut group = Vec::with_capacity(end - start);
        for index in start..end {
            let value = decode_value(bytes, dtype, index)?;
            if value.is_finite() {
                group.push(value);
            }
        }
        let (error, source) = symmetric_error_sums(&group, bits);
        error_squared += error;
        source_squared += source;
    }
    Ok(if source_squared > 0.0 {
        (error_squared / source_squared).sqrt()
    } else {
        0.0
    })
}

fn normalized_entropy_score(values: &[f32], bins: usize) -> f64 {
    if values.is_empty() || bins < 2 {
        return 0.0;
    }
    let min = values.iter().copied().fold(f32::INFINITY, f32::min);
    let max = values.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    if min >= max {
        return 0.0;
    }
    let range = (max - min) as f64;
    let mut histogram = vec![0usize; bins];
    for &value in values {
        let normalized = (value - min) as f64 / range;
        let index = ((normalized * bins as f64) as usize).min(bins - 1);
        histogram[index] += 1;
    }
    let total = values.len() as f64;
    let entropy = histogram
        .into_iter()
        .filter(|&count| count > 0)
        .map(|count| {
            let probability = count as f64 / total;
            -probability * probability.log2()
        })
        .sum::<f64>();
    entropy / (bins as f64).log2()
}

fn clipped_values(values: &[f32], low: f64, high: f64) -> Vec<f32> {
    let mut sorted = values.to_vec();
    sorted.sort_by(f32::total_cmp);
    let lower = percentile_sorted(&sorted, low);
    let upper = percentile_sorted(&sorted, high);
    values
        .iter()
        .map(|value| value.clamp(lower, upper))
        .collect()
}

fn percentile_sorted(values: &[f32], percentile: f64) -> f32 {
    if values.is_empty() {
        return 0.0;
    }
    let index = ((values.len() - 1) as f64 * percentile.clamp(0.0, 1.0)).round() as usize;
    values[index]
}

fn symmetric_nrmse(values: &[f32], bits: u8) -> f64 {
    let (error_squared, source_squared) = symmetric_error_sums(values, bits);
    if source_squared > 0.0 {
        (error_squared / source_squared).sqrt()
    } else {
        0.0
    }
}

fn symmetric_error_sums(values: &[f32], bits: u8) -> (f64, f64) {
    let qmax = ((1u32 << (bits - 1)) - 1) as f64;
    let absmax = values
        .iter()
        .map(|value| value.abs() as f64)
        .fold(0.0f64, f64::max);
    if absmax == 0.0 || values.is_empty() {
        return (0.0, 0.0);
    }
    let scale = absmax / qmax;
    values.iter().fold(
        (0.0, 0.0),
        |(mut error_squared, mut source_squared), &value| {
            let source = value as f64;
            let quantized = (source / scale).round().clamp(-qmax, qmax);
            let restored = quantized * scale;
            error_squared += (source - restored).powi(2);
            source_squared += source.powi(2);
            (error_squared, source_squared)
        },
    )
}

fn decode_value(bytes: &[u8], dtype: &str, index: usize) -> Result<f32> {
    let width = dtype_size(dtype).ok_or_else(|| anyhow!("unsupported dtype {dtype}"))?;
    let start = index
        .checked_mul(width)
        .ok_or_else(|| anyhow!("tensor byte index overflow"))?;
    let raw = bytes
        .get(start..start + width)
        .ok_or_else(|| anyhow!("tensor sample index {index} exceeds byte range"))?;
    match dtype {
        "BF16" => {
            let bits = u16::from_le_bytes(raw.try_into().expect("BF16 width"));
            Ok(f32::from_bits((bits as u32) << 16))
        }
        "F16" => {
            let bits = u16::from_le_bytes(raw.try_into().expect("F16 width"));
            Ok(f16::from_bits(bits).to_f32())
        }
        "F32" => Ok(f32::from_le_bytes(raw.try_into().expect("F32 width"))),
        _ => bail!("unsupported dtype {dtype}"),
    }
}

fn dtype_size(dtype: &str) -> Option<usize> {
    match dtype {
        "BF16" | "F16" => Some(2),
        "F32" => Some(4),
        _ => None,
    }
}

fn classify_family(name: &str) -> String {
    let lower = name.to_ascii_lowercase();
    let family = if lower.contains("text_embedding") {
        "text_embedding"
    } else if lower.contains("code_predictor") && lower.contains("lm_head") {
        "code_predictor_head"
    } else if lower.contains("code_predictor") && lower.contains("codec_embedding") {
        "code_predictor_embedding"
    } else if lower.contains("quantizer") || lower.contains("codebook") {
        "codec_quantizer"
    } else if lower.contains("conv") {
        "codec_convolution"
    } else if lower.contains("self_attn") || lower.contains("attention") {
        "attention"
    } else if lower.contains("mlp") || lower.contains("proj") || lower.contains("linear") {
        "feed_forward_or_projection"
    } else if lower.contains("norm") || lower.ends_with(".bias") || lower.ends_with(".scale") {
        "norm_scale_or_bias"
    } else if lower.ends_with(".weight") {
        "other_weight"
    } else {
        "other"
    };
    family.to_string()
}

fn sha256_file(path: &Path) -> Result<String> {
    let file = File::open(path)?;
    let mut reader = BufReader::with_capacity(1024 * 1024, file);
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 1024 * 1024];
    loop {
        let read = reader.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn sorted_unique(values: &[usize]) -> Vec<usize> {
    let mut values = values.to_vec();
    values.sort_unstable();
    values.dedup();
    values
}

#[cfg(test)]
mod tests {
    use super::*;

    use std::fs;

    use tempfile::TempDir;

    fn write_fixture(path: &Path, tensors: &[(&str, &str, Vec<u64>, Vec<u8>)]) {
        let mut header = serde_json::Map::new();
        let mut data = Vec::new();
        for (name, dtype, shape, bytes) in tensors {
            let start = data.len() as u64;
            data.extend_from_slice(bytes);
            let end = data.len() as u64;
            header.insert(
                (*name).to_string(),
                serde_json::json!({
                    "dtype": dtype,
                    "shape": shape,
                    "data_offsets": [start, end]
                }),
            );
        }
        let mut header_bytes = serde_json::to_vec(&header).unwrap();
        while (8 + header_bytes.len()) % 8 != 0 {
            header_bytes.push(b' ');
        }
        let mut file = File::create(path).unwrap();
        file.write_all(&(header_bytes.len() as u64).to_le_bytes())
            .unwrap();
        file.write_all(&header_bytes).unwrap();
        file.write_all(&data).unwrap();
    }

    fn f32_bytes(values: &[f32]) -> Vec<u8> {
        values
            .iter()
            .flat_map(|value| value.to_le_bytes())
            .collect()
    }

    fn bf16_bytes(values: &[f32]) -> Vec<u8> {
        values
            .iter()
            .flat_map(|value| ((value.to_bits() >> 16) as u16).to_le_bytes())
            .collect()
    }

    #[test]
    fn analyzes_known_partitions_deterministically() {
        let temp = TempDir::new().unwrap();
        fs::create_dir(temp.path().join("speech_tokenizer")).unwrap();
        let values = (0..4096)
            .map(|index| (index as f32 - 2048.0) / 2048.0)
            .collect::<Vec<_>>();
        write_fixture(
            &temp.path().join("model.safetensors"),
            &[(
                "talker.model.layers.0.mlp.up_proj.weight",
                "BF16",
                vec![64, 64],
                bf16_bytes(&values),
            )],
        );
        write_fixture(
            &temp.path().join("speech_tokenizer/model.safetensors"),
            &[(
                "decoder.pre_conv.conv.weight",
                "F32",
                vec![64, 64],
                f32_bytes(&values),
            )],
        );

        let options = AnalyzeOptions {
            sample_size: 1024,
            ..AnalyzeOptions::default()
        };
        let first = analyze_model_dir(temp.path(), &options).unwrap();
        let second = analyze_model_dir(temp.path(), &options).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.files[0].partition, "talker");
        assert_eq!(first.files[1].partition, "speech_tokenizer_codec");
        assert_eq!(
            first.files[0].tensors[0].evidence_level,
            "static_distribution"
        );
        let diagnostics = first.files[0].tensors[0].diagnostics.as_ref().unwrap();
        assert!(diagnostics.normalized_entropy.contains_key("256"));
        assert!(diagnostics.groupwise_q8_nrmse.contains_key("128"));
        assert!(diagnostics.per_tensor_q8_nrmse < diagnostics.per_tensor_q4_nrmse);
    }

    #[test]
    fn rejects_overlapping_tensor_ranges() {
        let temp = TempDir::new().unwrap();
        let path = temp.path().join("bad.safetensors");
        let header = serde_json::json!({
            "a": {"dtype":"F32","shape":[2,2],"data_offsets":[0,16]},
            "b": {"dtype":"F32","shape":[2,2],"data_offsets":[8,24]}
        });
        let header_bytes = serde_json::to_vec(&header).unwrap();
        let mut file = File::create(&path).unwrap();
        file.write_all(&(header_bytes.len() as u64).to_le_bytes())
            .unwrap();
        file.write_all(&header_bytes).unwrap();
        file.write_all(&[0u8; 24]).unwrap();
        drop(file);
        let file = File::open(&path).unwrap();
        let mmap = unsafe { MmapOptions::new().map(&file).unwrap() };
        let (base, tensors) = parse_header(&mmap, &path).unwrap();
        let error =
            validate_tensor_layout(&tensors, mmap.len() as u64, base as u64, &path).unwrap_err();
        assert!(error.to_string().contains("overlap"));
    }

    #[test]
    fn refuses_report_inside_model_directory_or_overwrite() {
        let temp = TempDir::new().unwrap();
        let report = StaticReport {
            schema: REPORT_SCHEMA.to_string(),
            model_snapshot_name: "fixture".to_string(),
            sample_strategy: "fixture".to_string(),
            sample_size: 128,
            min_elements: 1,
            entropy_bins: vec![64],
            group_sizes: vec![32],
            files: Vec::new(),
        };
        let inside = temp.path().join("report.json");
        let error = write_report(&report, Some(&inside), temp.path()).unwrap_err();
        assert!(error.to_string().contains("outside the model"));

        let outside_dir = TempDir::new().unwrap();
        let outside = outside_dir.path().join("report.json");
        write_report(&report, Some(&outside), temp.path()).unwrap();
        let error = write_report(&report, Some(&outside), temp.path()).unwrap_err();
        assert!(error.to_string().contains("refusing to overwrite"));
    }

    #[test]
    fn entropy_and_quantization_behave_on_structured_values() {
        let values = (0..4096)
            .map(|index| ((index % 17) as f32 - 8.0) / 8.0)
            .collect::<Vec<_>>();
        let entropy = normalized_entropy_score(&values, 64);
        assert!(entropy > 0.4 && entropy < 0.8);
        assert!(symmetric_nrmse(&values, 8) < symmetric_nrmse(&values, 4));
    }
}
