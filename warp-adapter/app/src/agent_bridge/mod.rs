mod registry;
mod server;

pub use registry::AgentBridgeRegistry;

use warpui::AppContext;

pub fn init(ctx: &mut AppContext) {
    ctx.add_singleton_model(|model_ctx| {
        let spawner = model_ctx.spawner();
        let bg = model_ctx.background_executor();
        server::start(spawner, bg);
        AgentBridgeRegistry::new(model_ctx)
    });
}
