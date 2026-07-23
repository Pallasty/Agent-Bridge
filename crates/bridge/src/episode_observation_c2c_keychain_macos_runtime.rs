//! Explicit C2C-B attachment bridge; it never receives custody material.

use crate::episode_observation_curation_batch::{
    CurationBatchObservationAttempt, CurationBatchObservationCapability,
    CurationBatchObservationError,
};
use crate::hub::HubBuilder;
use ab_store::episode_observation_c2_keychain_macos_runtime::{
    CurationBatchObservationError as StoreError, ExplicitKeychainMacosAttempt,
    ExplicitKeychainMacosHandle,
};
use ab_store::SqliteStore;
use async_trait::async_trait;
use std::sync::Arc;

struct Observer {
    handle: Arc<ExplicitKeychainMacosHandle>,
}
struct Attempt(ExplicitKeychainMacosAttempt);

fn map(error: StoreError) -> CurationBatchObservationError {
    match error {
        StoreError::Begin | StoreError::Unavailable => CurationBatchObservationError::Begin,
        StoreError::Item => CurationBatchObservationError::Item,
        StoreError::Close => CurationBatchObservationError::Close,
    }
}

/// Attaches the observer only after store-side Keychain readiness succeeds.
pub fn attach_explicit_keychain_macos_observer(
    builder: HubBuilder,
    store: Arc<SqliteStore>,
) -> HubBuilder {
    let observer = ExplicitKeychainMacosHandle::try_new(store).map(|handle| {
        Arc::new(Observer {
            handle: Arc::new(handle),
        }) as Arc<dyn CurationBatchObservationCapability>
    });
    attach_observer(builder, observer)
}

fn attach_observer(
    builder: HubBuilder,
    observer: Result<Arc<dyn CurationBatchObservationCapability>, StoreError>,
) -> HubBuilder {
    match observer {
        Ok(observer) => builder.curation_batch_observer(observer),
        Err(_) => builder,
    }
}

#[async_trait]
impl CurationBatchObservationCapability for Observer {
    async fn begin(
        &self,
    ) -> Result<Box<dyn CurationBatchObservationAttempt>, CurationBatchObservationError> {
        self.handle
            .begin()
            .await
            .map(|attempt| Box::new(Attempt(attempt)) as Box<dyn CurationBatchObservationAttempt>)
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
    use crate::hub::Hub;

    #[test]
    fn unavailable_store_handle_injects_no_observer() {
        let hub = attach_observer(Hub::builder(), Err(StoreError::Unavailable)).build();
        assert!(hub.curation_batch_observer.is_none());
    }
}
