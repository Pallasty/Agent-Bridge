//! Shared diagnostic classification for MCP tool-error telemetry.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ToolErrorDiagnosticClass {
    ExpectedConfirmation,
    ExpectedSafetyGate,
    ExpectedInputValidation,
    ExpectedRuntimeUnavailable,
    UnclassifiedError,
}

impl ToolErrorDiagnosticClass {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::ExpectedConfirmation => "expected_confirmation",
            Self::ExpectedSafetyGate => "expected_safety_gate",
            Self::ExpectedInputValidation => "expected_input_validation",
            Self::ExpectedRuntimeUnavailable => "expected_runtime_unavailable",
            Self::UnclassifiedError => "unclassified_error",
        }
    }

    pub(crate) fn is_expected(self) -> bool {
        self != Self::UnclassifiedError
    }
}

pub(crate) fn classify_tool_error(tool_name: &str, message: &str) -> ToolErrorDiagnosticClass {
    if is_expected_confirmation_error(tool_name, message) {
        ToolErrorDiagnosticClass::ExpectedConfirmation
    } else if is_expected_safety_gate(tool_name, message) {
        ToolErrorDiagnosticClass::ExpectedSafetyGate
    } else if is_expected_input_validation(tool_name, message) {
        ToolErrorDiagnosticClass::ExpectedInputValidation
    } else if is_expected_runtime_unavailable(tool_name, message) {
        ToolErrorDiagnosticClass::ExpectedRuntimeUnavailable
    } else {
        ToolErrorDiagnosticClass::UnclassifiedError
    }
}

fn is_expected_confirmation_error(tool_name: &str, message: &str) -> bool {
    tool_name == "agent_session_reconcile"
        && message.contains("requires apply_confirmation=\"finalise_stale_sessions\"")
}

fn is_expected_safety_gate(tool_name: &str, message: &str) -> bool {
    tool_name == "desktop_action" && message.contains("host_mutation_not_exposed")
}

fn is_expected_input_validation(tool_name: &str, message: &str) -> bool {
    match tool_name {
        "memory_save" => matches!(
            message,
            "missing or empty 'key'" | "missing or empty 'kind'"
        ),
        "work_memory" => message == "get requires key",
        _ => false,
    }
}

fn is_expected_runtime_unavailable(tool_name: &str, message: &str) -> bool {
    tool_name.starts_with("mobile_")
        && (message.contains("spawn adb failed")
            || message.contains("adb not on PATH")
            || message.contains("No Android devices")
            || message.contains("no Android devices"))
}
