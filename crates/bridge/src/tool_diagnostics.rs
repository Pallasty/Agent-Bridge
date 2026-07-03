//! Shared diagnostic classification for MCP tool-error telemetry.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ToolErrorDiagnosticClass {
    ExpectedConfirmation,
    ExpectedSafetyGate,
    ExpectedInputValidation,
    ExpectedLookupMiss,
    ExpectedRuntimeUnavailable,
    UnclassifiedError,
}

impl ToolErrorDiagnosticClass {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::ExpectedConfirmation => "expected_confirmation",
            Self::ExpectedSafetyGate => "expected_safety_gate",
            Self::ExpectedInputValidation => "expected_input_validation",
            Self::ExpectedLookupMiss => "expected_lookup_miss",
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
    } else if is_expected_lookup_miss(tool_name, message) {
        ToolErrorDiagnosticClass::ExpectedLookupMiss
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
        // Retired producer (get now derives the slot key when key is omitted);
        // kept so historical ring-buffer rows inside the audit window still
        // classify as benign.
        "work_memory" => message == "get requires key",
        "changes_digest" => {
            message
                == "invalid argument: unknown scope 'working'; expected working_tree|staged|last_commit|branch_vs_main"
        }
        _ => false,
    }
}

fn is_expected_lookup_miss(tool_name: &str, message: &str) -> bool {
    match tool_name {
        "plan_load" => message.starts_with("plan not found: "),
        // Since get falls back to the derived slot key, probing an empty slot
        // is a routine outcome, not a tool failure.
        "work_memory" => message == "work memory key not found",
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classifies_changes_digest_working_alias_tail_as_expected_validation() {
        assert_eq!(
            classify_tool_error(
                "changes_digest",
                "invalid argument: unknown scope 'working'; expected working_tree|staged|last_commit|branch_vs_main",
            ),
            ToolErrorDiagnosticClass::ExpectedInputValidation
        );
        assert_eq!(
            classify_tool_error(
                "changes_digest",
                "invalid argument: unknown scope 'banana'; expected working_tree|staged|last_commit|branch_vs_main",
            ),
            ToolErrorDiagnosticClass::UnclassifiedError
        );
    }

    #[test]
    fn classifies_work_memory_empty_slot_miss_as_expected_lookup_miss() {
        assert_eq!(
            classify_tool_error("work_memory", "work memory key not found"),
            ToolErrorDiagnosticClass::ExpectedLookupMiss
        );
        // Historical ring rows from the retired keyless-get validation error
        // stay benign within the audit window.
        assert_eq!(
            classify_tool_error("work_memory", "get requires key"),
            ToolErrorDiagnosticClass::ExpectedInputValidation
        );
        assert_eq!(
            classify_tool_error("work_memory", "key exists but is not work_memory"),
            ToolErrorDiagnosticClass::UnclassifiedError
        );
    }
}
