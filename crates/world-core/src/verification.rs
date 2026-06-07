use crate::ids::ActionId;
use crate::model::{AdapterEvidence, TargetRef};
use crate::schema::SCHEMA_VERIFICATION;
use serde::{Deserialize, Serialize};
use thiserror::Error;

pub type Result<T> = std::result::Result<T, WorldCoreError>;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum WorldCoreError {
    #[error("{verdict} verification requires a stable reason")]
    MissingReason { verdict: Verdict },

    #[error("verified verification requires verified_to")]
    MissingVerifiedTo,

    #[error("{verdict} verification must not set verified_to")]
    VerifiedToNotAllowed { verdict: Verdict },

    #[error("human decision cannot set changes_world_verdict=true")]
    HumanDecisionChangesVerification,

    #[error("invalid ledger snapshot schema: {0}")]
    InvalidLedgerSnapshotSchema(String),

    #[error("action already exists: {0}")]
    DuplicateAction(String),

    #[error("rollback group already exists: {0}")]
    DuplicateRollbackGroup(String),

    #[error("rollback group not found: {0}")]
    RollbackGroupNotFound(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Verdict {
    Verified,
    NotVerified,
    Blocked,
}

impl std::fmt::Display for Verdict {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Verified => f.write_str("verified"),
            Self::NotVerified => f.write_str("not_verified"),
            Self::Blocked => f.write_str("blocked"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Verification {
    pub schema: String,
    pub action_id: Option<ActionId>,
    pub verdict: Verdict,
    pub reason: Option<String>,
    pub method: String,
    pub verified_to: Option<TargetRef>,
    pub evidence: AdapterEvidence,
}

impl Verification {
    pub fn new(
        action_id: Option<ActionId>,
        verdict: Verdict,
        reason: Option<String>,
        method: impl Into<String>,
        verified_to: Option<TargetRef>,
        evidence: AdapterEvidence,
    ) -> Result<Self> {
        validate_verification(verdict, reason.as_deref(), verified_to.as_ref())?;
        Ok(Self {
            schema: SCHEMA_VERIFICATION.to_string(),
            action_id,
            verdict,
            reason,
            method: method.into(),
            verified_to,
            evidence,
        })
    }
}

pub fn validate_verification(
    verdict: Verdict,
    reason: Option<&str>,
    verified_to: Option<&TargetRef>,
) -> Result<()> {
    match verdict {
        Verdict::Verified => {
            if verified_to.is_none() {
                return Err(WorldCoreError::MissingVerifiedTo);
            }
        }
        Verdict::NotVerified | Verdict::Blocked => {
            if reason.map(str::trim).unwrap_or_default().is_empty() {
                return Err(WorldCoreError::MissingReason { verdict });
            }
            if verified_to.is_some() {
                return Err(WorldCoreError::VerifiedToNotAllowed { verdict });
            }
        }
    }
    Ok(())
}
