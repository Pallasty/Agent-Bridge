//! Explicit local adapter for the fixed asset recipe; no daemon or store startup.

use std::{ffi::OsString, path::Path, process::ExitCode};

use anyhow::{ensure, Context, Result};
use serde_json::Value;

fn inspect_args(args: &[OsString]) -> Result<Value> {
    ensure!(
        (1..=2).contains(&args.len()),
        "Usage: asset_inspect PATH [EXPECTED_SHA256]"
    );
    let expected = args
        .get(1)
        .map(|value| value.to_str().context("expected digest must be UTF-8"))
        .transpose()?;
    ab_bridge::asset_inspect::inspect_file(Path::new(&args[0]), expected)
}

fn main() -> ExitCode {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args == [OsString::from("--help")] {
        println!("Usage: asset_inspect PATH [EXPECTED_SHA256]");
        return ExitCode::SUCCESS;
    }
    match inspect_args(&args) {
        Ok(report) => {
            println!("{report}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("{error:#}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn png_file() -> Result<(tempfile::TempDir, OsString)> {
        let directory = tempfile::tempdir()?;
        let path = directory.path().join("input.bin");
        let file = std::fs::File::create(&path)?;
        let mut encoder = png::Encoder::new(file, 2, 1);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder
            .write_header()?
            .write_image_data(&[90, 100, 110, 255, 0, 0, 0, 0])?;
        Ok((directory, path.into_os_string()))
    }

    #[test]
    fn test_inspects_file_and_round_trips_expected_digest() -> Result<()> {
        let (_directory, path) = png_file()?;
        let report = inspect_args(std::slice::from_ref(&path))?;
        assert_eq!(report["format"], "png");
        assert_eq!(report["details"]["width"], 2);
        assert_eq!(report["visual_quality_reviewed"], false);
        let digest = report["sha256"]
            .as_str()
            .ok_or_else(|| anyhow::anyhow!("missing digest"))?;
        let checked = inspect_args(&[path, OsString::from(digest)])?;
        assert_eq!(checked["expected_sha256_matches"], true);
        Ok(())
    }

    #[test]
    fn test_rejects_digest_mismatch() -> Result<()> {
        let (_directory, path) = png_file()?;
        let error = inspect_args(&[path, OsString::from("0".repeat(64))])
            .err()
            .ok_or_else(|| anyhow::anyhow!("bad digest was accepted"))?;
        assert!(format!("{error:#}").contains("SHA-256 mismatch"));
        Ok(())
    }

    #[test]
    fn test_rejects_missing_and_extra_arguments() {
        for args in [vec![], vec!["a".into(), "b".into(), "c".into()]] {
            let error = inspect_args(&args).err().map(|error| error.to_string());
            assert!(error.is_some_and(|message| message.contains("Usage:")));
        }
    }
}
