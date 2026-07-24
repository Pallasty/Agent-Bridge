use serde::{Deserialize, Serialize};
use uuid::Uuid;

macro_rules! id_newtype {
    ($name:ident, $prefix:expr) => {
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
        #[serde(transparent)]
        pub struct $name(pub String);

        impl $name {
            pub fn new() -> Self {
                Self(format!("{}-{}", $prefix, Uuid::new_v4()))
            }

            pub fn from_raw(raw: impl Into<String>) -> Self {
                Self(raw.into())
            }

            pub fn as_str(&self) -> &str {
                &self.0
            }
        }

        impl Default for $name {
            fn default() -> Self {
                Self::new()
            }
        }

        impl std::fmt::Display for $name {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                f.write_str(&self.0)
            }
        }
    };
}

id_newtype!(WorldId, "world");
id_newtype!(BranchId, "branch");
id_newtype!(EntityId, "entity");
id_newtype!(ParticipantId, "participant");
id_newtype!(ActionId, "action");
id_newtype!(ActionQueryId, "action-query");
id_newtype!(EventId, "event");
id_newtype!(EventQueryId, "event-query");
id_newtype!(FeedbackId, "feedback");
id_newtype!(FeedbackQueryId, "feedback-query");
id_newtype!(RollbackGroupId, "rollback");
id_newtype!(RollbackQueryId, "rollback-query");
id_newtype!(EvidenceQueryId, "evidence-query");
id_newtype!(BodyId, "body");
id_newtype!(IntentId, "intent");
id_newtype!(ReceiptId, "receipt");
id_newtype!(LeaseId, "lease");
