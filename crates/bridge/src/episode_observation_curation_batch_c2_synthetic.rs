//! Crate-private adaptation of the store-owned synthetic C2 attempt to C1.

use crate::episode_observation_curation_batch::{
    CurationBatchObservationAttempt, CurationBatchObservationCapability,
    CurationBatchObservationError,
};
use ab_store::episode_observation_c2_synthetic::{
    CurationBatchObservationError as StoreError, CurationBatchObservationHandle,
};
use async_trait::async_trait;
use std::sync::Arc;

pub(crate) struct SyntheticStoreObserver {
    handle: Arc<CurationBatchObservationHandle>,
}
pub(crate) fn synthetic_store_observer(
    handle: Arc<CurationBatchObservationHandle>,
) -> Arc<dyn CurationBatchObservationCapability> {
    Arc::new(SyntheticStoreObserver { handle })
}
fn map(error: StoreError) -> CurationBatchObservationError {
    match error {
        StoreError::Begin => CurationBatchObservationError::Begin,
        StoreError::Item => CurationBatchObservationError::Item,
        StoreError::Close => CurationBatchObservationError::Close,
    }
}
struct Attempt(ab_store::episode_observation_c2_synthetic::CurationBatchObservationAttempt);
#[async_trait]
impl CurationBatchObservationCapability for SyntheticStoreObserver {
    async fn begin(
        &self,
    ) -> Result<Box<dyn CurationBatchObservationAttempt>, CurationBatchObservationError> {
        self.handle
            .begin()
            .await
            .map(|a| Box::new(Attempt(a)) as Box<dyn CurationBatchObservationAttempt>)
            .map_err(map)
    }
}
#[async_trait]
impl CurationBatchObservationAttempt for Attempt {
    async fn observe_saved(
        &mut self,
        key: &str,
        ordinal: u32,
    ) -> Result<(), CurationBatchObservationError> {
        self.0.observe_saved(key, ordinal).await.map_err(map)
    }
    async fn finish(self: Box<Self>, count: u32) -> Result<(), CurationBatchObservationError> {
        self.0.finish(count).await.map_err(map)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn store_errors_map_to_the_existing_coarse_c1_errors() {
        assert_eq!(map(StoreError::Begin), CurationBatchObservationError::Begin);
        assert_eq!(map(StoreError::Item), CurationBatchObservationError::Item);
        assert_eq!(map(StoreError::Close), CurationBatchObservationError::Close);
    }
}
