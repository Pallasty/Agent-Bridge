//! Live Semantic World Runtime core schema and in-memory ledger.
//!
//! This crate intentionally has no dependency on `ab-bridge`, MCP, browser,
//! renderer, or engine crates. It holds portable semantic world types only.

pub mod event_query;
pub mod evidence_query;
pub mod feedback_query;
pub mod ids;
pub mod ledger;
pub mod model;
pub mod rollback_query;
pub mod schema;
pub mod verification;

pub use event_query::*;
pub use evidence_query::*;
pub use feedback_query::*;
pub use ids::*;
pub use ledger::*;
pub use model::*;
pub use rollback_query::*;
pub use schema::*;
pub use verification::*;

#[cfg(test)]
mod tests;
