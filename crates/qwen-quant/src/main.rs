use std::path::PathBuf;

use ab_qwen_quant::{analyze_model_dir, write_report, AnalyzeOptions};
use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Debug, Parser)]
#[command(
    name = "ab-qwen-quant",
    about = "Read-only Qwen3-TTS SafeTensors inventory and quantization diagnostics"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Analyze known Qwen3-TTS talker and speech-tokenizer SafeTensors files.
    Analyze {
        /// Complete local Qwen3-TTS model snapshot.
        #[arg(long)]
        model_dir: PathBuf,

        /// Optional report path. Existing files are never overwritten.
        #[arg(long)]
        output: Option<PathBuf>,

        /// Maximum evenly spaced values used for distribution diagnostics.
        #[arg(long, default_value_t = 8192)]
        sample_size: usize,

        /// Tensors below this element count remain inventory-only.
        #[arg(long, default_value_t = 4096)]
        min_elements: u64,

        /// Histogram sizes used for normalized Shannon entropy.
        #[arg(long, value_delimiter = ',', default_value = "64,256,1024")]
        entropy_bins: Vec<usize>,

        /// Real tensor group sizes sampled for local reconstruction error.
        #[arg(long, value_delimiter = ',', default_value = "32,64,128,256")]
        group_sizes: Vec<usize>,

        /// Stream SHA-256 over each source SafeTensors file.
        #[arg(long)]
        sha256: bool,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Analyze {
            model_dir,
            output,
            sample_size,
            min_elements,
            entropy_bins,
            group_sizes,
            sha256,
        } => {
            let options = AnalyzeOptions {
                sample_size,
                min_elements,
                entropy_bins,
                group_sizes,
                include_sha256: sha256,
            };
            let report = analyze_model_dir(&model_dir, &options)?;
            write_report(&report, output.as_deref(), &model_dir)?;
        }
    }
    Ok(())
}
