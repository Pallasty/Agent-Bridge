use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),

    #[error("serde: {0}")]
    Serde(#[from] serde_json::Error),

    #[error("rpc: {0}")]
    Rpc(String),

    #[error("backend: {0}")]
    Backend(String),

    #[error("not found: {0}")]
    NotFound(String),

    #[error("invalid argument: {0}")]
    InvalidArgument(String),
}

pub type Result<T> = std::result::Result<T, Error>;
