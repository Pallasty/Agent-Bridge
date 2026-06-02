use serde_json::{json, Value};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RendererSource {
    ProjectedAvatar,
    ScopedRawPet,
    IdleFallback,
}

impl RendererSource {
    fn as_str(&self) -> &'static str {
        match self {
            Self::ProjectedAvatar => "projected_avatar",
            Self::ScopedRawPet => "scoped_raw_pet",
            Self::IdleFallback => "idle_fallback",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RendererScope {
    pub project: String,
    pub cwd: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RendererStateSelection {
    pub source: RendererSource,
    pub state: Value,
    pub fallback_reason: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RendererPlan {
    pub track: String,
    pub renderer_token: String,
    pub asset_route: Option<String>,
    pub fallback_reason: Option<String>,
}

fn non_empty_str<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

fn raw_pet_matches_scope(scope: &RendererScope, raw_pet: &Value) -> bool {
    if non_empty_str(raw_pet, "project") != Some(scope.project.as_str()) {
        return false;
    }

    match (&scope.cwd, non_empty_str(raw_pet, "cwd")) {
        (Some(expected), Some(actual)) => actual == expected,
        (Some(_), None) => false,
        (None, _) => true,
    }
}

fn idle_state(scope: &RendererScope) -> Value {
    json!({
        "agent_avatar_protocol": 1,
        "project": scope.project,
        "cwd": scope.cwd,
        "mode": "idle",
        "activity_state": "idle"
    })
}

pub fn select_renderer_state(
    scope: &RendererScope,
    projected_avatar: Option<&Value>,
    raw_pet: Option<&Value>,
) -> RendererStateSelection {
    if let Some(state) = projected_avatar.filter(|value| value.is_object()) {
        return RendererStateSelection {
            source: RendererSource::ProjectedAvatar,
            state: state.clone(),
            fallback_reason: None,
        };
    }

    if let Some(state) = raw_pet.filter(|value| value.is_object()) {
        if raw_pet_matches_scope(scope, state) {
            return RendererStateSelection {
                source: RendererSource::ScopedRawPet,
                state: state.clone(),
                fallback_reason: None,
            };
        }

        return RendererStateSelection {
            source: RendererSource::IdleFallback,
            state: idle_state(scope),
            fallback_reason: Some("raw_pet_scope_mismatch".to_string()),
        };
    }

    RendererStateSelection {
        source: RendererSource::IdleFallback,
        state: idle_state(scope),
        fallback_reason: Some("no_state_available".to_string()),
    }
}

pub fn renderer_plan_from_state(state: &Value) -> RendererPlan {
    let mode = non_empty_str(state, "mode").unwrap_or("idle");
    let (track, renderer_token, asset_route, fallback_reason) = match mode {
        "idle" => (
            "idle_breathe",
            "xiao_shu::idle_breathe::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"),
            None,
        ),
        "orienting" => ("focused_review", "xiao_shu::focused_review::low", None, None),
        "reviewing" => (
            "look_sideways",
            "xiao_shu::look_sideways::medium",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v2"),
            None,
        ),
        "working" => (
            "sorting_glow",
            "xiao_shu::sorting_glow::medium",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v3"),
            None,
        ),
        "waiting_for_user" => ("waiting_for_user", "xiao_shu::waiting_for_user::low", None, None),
        "failed" => ("mismatch", "xiao_shu::mismatch::medium", None, None),
        "verified" => (
            "completion_nod",
            "xiao_shu::completion_nod::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-completion-nod-v1"),
            None,
        ),
        "handoff" => (
            "idle_breathe",
            "xiao_shu::idle_breathe::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"),
            None,
        ),
        _ => (
            "idle_breathe",
            "xiao_shu::idle_breathe::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"),
            Some("unknown_mode"),
        ),
    };

    RendererPlan {
        track: track.to_string(),
        renderer_token: renderer_token.to_string(),
        asset_route: asset_route.map(ToString::to_string),
        fallback_reason: fallback_reason.map(ToString::to_string),
    }
}

pub fn renderer_payload_from_sources(
    scope: &RendererScope,
    projected_avatar: Option<&Value>,
    raw_pet: Option<&Value>,
) -> Value {
    let selection = select_renderer_state(scope, projected_avatar, raw_pet);
    let plan = renderer_plan_from_state(&selection.state);

    json!({
        "surface": "linux_codex_avatar_renderer_state",
        "schema": 1,
        "read_only": true,
        "project": scope.project,
        "cwd": scope.cwd,
        "selection": {
            "source": selection.source.as_str(),
            "fallback_reason": selection.fallback_reason,
        },
        "state": selection.state,
        "plan": {
            "track": plan.track,
            "renderer_token": plan.renderer_token,
            "asset_route": plan.asset_route,
            "fallback_reason": plan.fallback_reason,
        },
        "safety": {
            "sidecar_only": true,
            "writes_files": false,
            "mutates_renderer": false,
            "codex_pet_package_mutation": false,
            "emits_audio": false,
            "emits_notification": false,
            "controls_desktop": false,
        }
    })
}
