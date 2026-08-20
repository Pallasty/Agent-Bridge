#!/usr/bin/env swift

import AppKit
import ApplicationServices
import Foundation

private let schema = "macos_ax_focus_window/v0"
private let defaultVerifyTimeoutMs = 750

private struct Options {
    let pid: pid_t
    let bundleID: String
    let axIdentifier: String?
    let windowIndex: Int?
    let expectedTitle: String?
    let expectedTitleProvided: Bool
    let expectedRole: String?
    let verifyTimeoutMs: Int
    let compact: Bool

    var selectorMode: String {
        axIdentifier == nil ? "sample_index_with_constraints" : "ax_identifier"
    }
}

private struct CLIError: Error, CustomStringConvertible {
    let description: String
}

private struct ForegroundIdentity {
    let pid: pid_t
    let bundleID: String?
    let name: String?
}

private struct WindowRecord {
    let index: Int
    let element: AXUIElement
    let axIdentifier: String?
    let axIdentifierReadOK: Bool
    let title: String?
    let titleReadOK: Bool
    let role: String?
    let roleReadOK: Bool
    let focused: Bool?
    let main: Bool?
}

private struct SurfaceSample {
    let foreground: ForegroundIdentity?
    let windows: [WindowRecord]
    let windowsError: AXError
    let focusedWindow: AXUIElement?
    let focusedWindowError: AXError
    let revision: String
}

private enum SelectorCompatibility {
    case exactMatch
    case definiteMismatch
    case indeterminate
}

private struct SelectorAssessment {
    let matches: [WindowRecord]
    let hiddenCandidates: [WindowRecord]
}

private struct PostflightAssessment {
    let windowsReadOK: Bool
    let focusedWindowReadOK: Bool
    let scopeStable: Bool
    let hiddenCandidateCount: Int
    let targetStillExact: Bool
    let currentTarget: WindowRecord?
    let exactTargetFocused: Bool

    var verified: Bool {
        windowsReadOK
            && focusedWindowReadOK
            && scopeStable
            && targetStillExact
            && exactTargetFocused
    }

    var readbackComplete: Bool {
        windowsReadOK && focusedWindowReadOK && scopeStable
    }
}

private func parseOptions(_ arguments: [String]) throws -> Options {
    var pidValue: pid_t?
    var bundleID: String?
    var axIdentifier: String?
    var windowIndex: Int?
    var expectedTitle: String?
    var expectedTitleProvided = false
    var expectedRole: String?
    var verifyTimeoutMs = defaultVerifyTimeoutMs
    var compact = false
    var seen = Set<String>()

    func unique(_ option: String) throws {
        guard seen.insert(option).inserted else {
            throw CLIError(description: "duplicate_option:\(option)")
        }
    }

    var cursor = 0
    while cursor < arguments.count {
        let option = arguments[cursor]
        if option == "--compact" {
            try unique(option)
            compact = true
            cursor += 1
            continue
        }

        let valueOptions: Set<String> = [
            "--pid",
            "--bundle-id",
            "--ax-identifier",
            "--window-index",
            "--expected-title",
            "--expected-role",
            "--verify-timeout-ms",
        ]
        guard valueOptions.contains(option) else {
            throw CLIError(description: "unknown_option:\(option)")
        }
        try unique(option)
        guard cursor + 1 < arguments.count else {
            throw CLIError(description: "missing_value:\(option)")
        }
        let value = arguments[cursor + 1]
        switch option {
        case "--pid":
            guard let parsed = Int64(value), parsed > 0, parsed <= Int64(Int32.max) else {
                throw CLIError(description: "invalid_pid:must_be_positive_int32")
            }
            pidValue = pid_t(parsed)
        case "--bundle-id":
            let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !normalized.isEmpty else {
                throw CLIError(description: "invalid_bundle_id:must_be_nonempty")
            }
            bundleID = normalized
        case "--ax-identifier":
            let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !normalized.isEmpty else {
                throw CLIError(description: "invalid_ax_identifier:must_be_nonempty")
            }
            axIdentifier = normalized
        case "--window-index":
            guard let parsed = Int(value), parsed >= 0 else {
                throw CLIError(description: "invalid_window_index:must_be_nonnegative_integer")
            }
            windowIndex = parsed
        case "--expected-title":
            expectedTitle = value
            expectedTitleProvided = true
        case "--expected-role":
            let normalized = value.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !normalized.isEmpty else {
                throw CLIError(description: "invalid_expected_role:must_be_nonempty")
            }
            expectedRole = normalized
        case "--verify-timeout-ms":
            guard let parsed = Int(value), (50 ... 2_000).contains(parsed) else {
                throw CLIError(description: "invalid_verify_timeout_ms:must_be_50_through_2000")
            }
            verifyTimeoutMs = parsed
        default:
            throw CLIError(description: "unknown_option:\(option)")
        }
        cursor += 2
    }

    guard let pidValue else {
        throw CLIError(description: "missing_required_option:--pid")
    }
    guard let bundleID else {
        throw CLIError(description: "missing_required_option:--bundle-id")
    }

    if axIdentifier != nil {
        guard windowIndex == nil else {
            throw CLIError(description: "invalid_selector:ax_identifier_and_window_index_are_exclusive")
        }
    } else {
        guard windowIndex != nil else {
            throw CLIError(description: "invalid_selector:ax_identifier_or_window_index_required")
        }
        guard expectedTitleProvided else {
            throw CLIError(description: "invalid_selector:index_requires_expected_title")
        }
        guard expectedRole != nil else {
            throw CLIError(description: "invalid_selector:index_requires_expected_role")
        }
    }

    // Kept explicit so a future parser refactor cannot silently drop the bound.
    precondition((50 ... 2_000).contains(verifyTimeoutMs))

    return Options(
        pid: pidValue,
        bundleID: bundleID,
        axIdentifier: axIdentifier,
        windowIndex: windowIndex,
        expectedTitle: expectedTitle,
        expectedTitleProvided: expectedTitleProvided,
        expectedRole: expectedRole,
        verifyTimeoutMs: verifyTimeoutMs,
        compact: compact
    )
}

private func nullIfNil(_ value: Any?) -> Any {
    value ?? NSNull()
}

private func foregroundIdentity() -> ForegroundIdentity? {
    guard let application = NSWorkspace.shared.frontmostApplication else {
        return nil
    }
    return ForegroundIdentity(
        pid: application.processIdentifier,
        bundleID: application.bundleIdentifier,
        name: application.localizedName
    )
}

private func foregroundJSON(_ identity: ForegroundIdentity?) -> Any {
    guard let identity else {
        return NSNull()
    }
    return [
        "pid": Int(identity.pid),
        "bundle_id": nullIfNil(identity.bundleID),
        "name": nullIfNil(identity.name),
    ] as [String: Any]
}

private func foregroundMatches(_ identity: ForegroundIdentity?, options: Options) -> Bool {
    identity?.pid == options.pid && identity?.bundleID == options.bundleID
}

private func sameForeground(_ lhs: ForegroundIdentity?, _ rhs: ForegroundIdentity?) -> Bool {
    lhs?.pid == rhs?.pid && lhs?.bundleID == rhs?.bundleID
}

private func copyAttribute(
    _ element: AXUIElement,
    _ attribute: CFString
) -> (CFTypeRef?, AXError) {
    var value: CFTypeRef?
    let error = AXUIElementCopyAttributeValue(element, attribute, &value)
    return (value, error)
}

private func stringAttribute(
    _ element: AXUIElement,
    _ attribute: CFString
) -> (value: String?, readOK: Bool) {
    let (value, error) = copyAttribute(element, attribute)
    guard error == .success, let string = value as? String else {
        return (nil, false)
    }
    return (string, true)
}

private func boolAttribute(_ element: AXUIElement, _ attribute: CFString) -> Bool? {
    let (value, error) = copyAttribute(element, attribute)
    guard error == .success else {
        return nil
    }
    return (value as? NSNumber)?.boolValue
}

private func readWindows(_ application: AXUIElement) -> ([WindowRecord], AXError) {
    let (value, error) = copyAttribute(application, kAXWindowsAttribute as CFString)
    guard error == .success else {
        return ([], error)
    }
    guard let elements = value as? [AXUIElement] else {
        return ([], .failure)
    }
    let records = elements.enumerated().map { index, element in
        let axIdentifier = stringAttribute(element, kAXIdentifierAttribute as CFString)
        let title = stringAttribute(element, kAXTitleAttribute as CFString)
        let role = stringAttribute(element, kAXRoleAttribute as CFString)
        return WindowRecord(
            index: index,
            element: element,
            axIdentifier: axIdentifier.value,
            axIdentifierReadOK: axIdentifier.readOK,
            title: title.value,
            titleReadOK: title.readOK,
            role: role.value,
            roleReadOK: role.readOK,
            focused: boolAttribute(element, kAXFocusedAttribute as CFString),
            main: boolAttribute(element, kAXMainAttribute as CFString)
        )
    }
    return (records, .success)
}

private func readFocusedWindow(_ application: AXUIElement) -> (AXUIElement?, AXError) {
    let (value, error) = copyAttribute(application, kAXFocusedWindowAttribute as CFString)
    guard error == .success else {
        return (nil, error)
    }
    guard let value, CFGetTypeID(value) == AXUIElementGetTypeID() else {
        return (nil, .failure)
    }
    let focusedWindow = value as! AXUIElement
    return (focusedWindow, .success)
}

private func elementsEqual(_ lhs: AXUIElement?, _ rhs: AXUIElement?) -> Bool {
    guard let lhs, let rhs else {
        return false
    }
    return CFEqual(lhs, rhs)
}

private func recordForElement(
    _ element: AXUIElement,
    in windows: [WindowRecord]
) -> WindowRecord? {
    windows.first { CFEqual($0.element, element) }
}

private func hexFNV1a64(_ text: String) -> String {
    var hash: UInt64 = 14_695_981_039_346_656_037
    for byte in text.utf8 {
        hash ^= UInt64(byte)
        hash &*= 1_099_511_628_211
    }
    return String(format: "fnv1a64:%016llx", hash)
}

private func worldRevision(
    foreground: ForegroundIdentity?,
    windows: [WindowRecord],
    focusedWindow: AXUIElement?
) -> String {
    let foregroundPart = [
        String(foreground?.pid ?? 0),
        foreground?.bundleID ?? "<nil>",
    ].joined(separator: "|")
    let windowParts = windows.map { window -> String in
        let focusedByApplication = elementsEqual(window.element, focusedWindow)
        return [
            String(window.index),
            window.axIdentifier ?? "<nil>",
            String(window.axIdentifierReadOK),
            window.title ?? "<nil>",
            String(window.titleReadOK),
            window.role ?? "<nil>",
            String(window.roleReadOK),
            String(focusedByApplication),
            window.focused.map(String.init) ?? "<nil>",
            window.main.map(String.init) ?? "<nil>",
        ].joined(separator: "|")
    }
    return hexFNV1a64(([foregroundPart] + windowParts).joined(separator: "\n"))
}

private func sampleSurface(_ application: AXUIElement) -> SurfaceSample {
    let foreground = foregroundIdentity()
    let (windows, windowsError) = readWindows(application)
    let (focusedWindow, focusedWindowError) = readFocusedWindow(application)
    return SurfaceSample(
        foreground: foreground,
        windows: windows,
        windowsError: windowsError,
        focusedWindow: focusedWindow,
        focusedWindowError: focusedWindowError,
        revision: worldRevision(
            foreground: foreground,
            windows: windows,
            focusedWindow: focusedWindow
        )
    )
}

private func selectorCompatibility(
    _ record: WindowRecord,
    options: Options
) -> SelectorCompatibility {
    // A successfully read mismatch is conclusive even when another selector
    // attribute is unreadable. Otherwise an unreadable required attribute
    // leaves this window compatible with the selector and therefore hidden.
    var requiredAttributeUnreadable = false

    func stringConstraintMatches(
        value: String?,
        readOK: Bool,
        expected: String
    ) -> Bool {
        guard readOK else {
            requiredAttributeUnreadable = true
            return true
        }
        return value == expected
    }

    if let axIdentifier = options.axIdentifier {
        guard stringConstraintMatches(
            value: record.axIdentifier,
            readOK: record.axIdentifierReadOK,
            expected: axIdentifier
        ) else {
            return .definiteMismatch
        }
        if options.expectedTitleProvided,
           !stringConstraintMatches(
               value: record.title,
               readOK: record.titleReadOK,
               expected: options.expectedTitle ?? ""
           )
        {
            return .definiteMismatch
        }
        if let expectedRole = options.expectedRole,
           !stringConstraintMatches(
               value: record.role,
               readOK: record.roleReadOK,
               expected: expectedRole
           )
        {
            return .definiteMismatch
        }
    } else {
        guard record.index == options.windowIndex else {
            return .definiteMismatch
        }
        guard stringConstraintMatches(
            value: record.title,
            readOK: record.titleReadOK,
            expected: options.expectedTitle ?? ""
        ) else {
            return .definiteMismatch
        }
        guard stringConstraintMatches(
            value: record.role,
            readOK: record.roleReadOK,
            expected: options.expectedRole ?? ""
        ) else {
            return .definiteMismatch
        }
    }

    return requiredAttributeUnreadable ? .indeterminate : .exactMatch
}

private func assessSelector(
    _ windows: [WindowRecord],
    options: Options
) -> SelectorAssessment {
    var matches = [WindowRecord]()
    var hiddenCandidates = [WindowRecord]()
    for window in windows {
        switch selectorCompatibility(window, options: options) {
        case .exactMatch:
            matches.append(window)
        case .indeterminate:
            hiddenCandidates.append(window)
        case .definiteMismatch:
            break
        }
    }
    return SelectorAssessment(matches: matches, hiddenCandidates: hiddenCandidates)
}

private func matchingWindows(_ windows: [WindowRecord], options: Options) -> [WindowRecord] {
    assessSelector(windows, options: options).matches
}

private func targetStillExact(
    original: WindowRecord,
    in windows: [WindowRecord],
    options: Options
) -> (Bool, WindowRecord?) {
    guard let current = recordForElement(original.element, in: windows) else {
        return (false, nil)
    }
    let matches = matchingWindows(windows, options: options)
    return (matches.count == 1 && CFEqual(matches[0].element, original.element), current)
}

private func assessPostflight(
    _ sample: SurfaceSample,
    original: WindowRecord,
    options: Options,
    baselineForeground: ForegroundIdentity?
) -> PostflightAssessment {
    let scopeStable = foregroundMatches(sample.foreground, options: options)
        && sameForeground(baselineForeground, sample.foreground)
    let selectorAssessment = sample.windowsError == .success
        ? assessSelector(sample.windows, options: options)
        : SelectorAssessment(matches: [], hiddenCandidates: [])
    // AXWindows is only complete enough for a selector proof when no window
    // remains a possible match behind an unreadable required attribute.
    let windowsReadOK = sample.windowsError == .success
        && selectorAssessment.hiddenCandidates.isEmpty
    let focusedWindowReadOK = sample.focusedWindowError == .success
    let exactResult = windowsReadOK
        ? targetStillExact(original: original, in: sample.windows, options: options)
        : (false, nil)
    let exactTargetFocused = windowsReadOK
        && focusedWindowReadOK
        && scopeStable
        && exactResult.0
        && elementsEqual(sample.focusedWindow, original.element)
    return PostflightAssessment(
        windowsReadOK: windowsReadOK,
        focusedWindowReadOK: focusedWindowReadOK,
        scopeStable: scopeStable,
        hiddenCandidateCount: selectorAssessment.hiddenCandidates.count,
        targetStillExact: exactResult.0,
        currentTarget: exactResult.1,
        exactTargetFocused: exactTargetFocused
    )
}

private func windowJSON(_ window: WindowRecord?) -> Any {
    guard let window else {
        return NSNull()
    }
    return [
        "index": window.index,
        "ax_identifier": nullIfNil(window.axIdentifier),
        "title": nullIfNil(window.title),
        "role": nullIfNil(window.role),
        "selector_attributes_read_ok": [
            "ax_identifier": window.axIdentifierReadOK,
            "title": window.titleReadOK,
            "role": window.roleReadOK,
        ],
        "focused": nullIfNil(window.focused),
        "main": nullIfNil(window.main),
    ] as [String: Any]
}

private func axErrorJSON(stage: String, error: AXError) -> [String: Any] {
    [
        "stage": stage,
        "code": Int(error.rawValue),
        "name": "AXError(\(error.rawValue))",
    ]
}

private func selectorJSON(_ options: Options) -> [String: Any] {
    [
        "mode": options.selectorMode,
        "ax_identifier": nullIfNil(options.axIdentifier),
        "window_index": nullIfNil(options.windowIndex),
        "expected_title": options.expectedTitleProvided
            ? nullIfNil(options.expectedTitle)
            : NSNull(),
        "expected_role": nullIfNil(options.expectedRole),
    ]
}

private func baseReceipt(compact: Bool) -> [String: Any] {
    _ = compact
    return [
        "schema": schema,
        "status": "error",
        "read_only": false,
        "operation": "focus_window",
        "permission": [
            "ax_trusted": NSNull(),
            "method": "AXIsProcessTrusted",
            "prompted": false,
        ],
        "authority": [
            "source": "owner_standing",
            "risk_rank": 1,
            "classification": "embodied_navigation",
            "prompt_required": false,
            "prompted": false,
        ],
        "target": NSNull(),
        "precondition": [
            "met": false,
            "reason_codes": [String](),
        ],
        "execution": [
            "attempted": false,
            "performed": false,
            "idempotent_noop": false,
            "primitive": NSNull(),
            "ax_error": NSNull(),
        ],
        "postcondition": [
            "met": false,
            "exact_target_focused": false,
            "target_still_exact": false,
            "foreground_unchanged": false,
            "windows_read_ok": false,
            "focused_window_read_ok": false,
            "scope_stable": false,
        ],
        "verification": [
            "verdict": "error",
            "reason_codes": [String](),
            "recover": [
                "safe_to_retry": false,
                "next": "inspect_receipt",
            ],
        ],
        "world_revision": [
            "before": NSNull(),
            "after": NSNull(),
        ],
        "foreground": [
            "before": NSNull(),
            "after": NSNull(),
            "changed": false,
            "restore_attempted": false,
            "restore_reason": "not_applicable_no_action",
        ],
        "visual_evidence": false,
    ]
}

private func emit(_ receipt: [String: Any], compact: Bool) {
    let writingOptions: JSONSerialization.WritingOptions = compact
        ? [.sortedKeys]
        : [.prettyPrinted, .sortedKeys]
    let payload: Data
    if JSONSerialization.isValidJSONObject(receipt),
       let serialized = try? JSONSerialization.data(withJSONObject: receipt, options: writingOptions)
    {
        payload = serialized
    } else {
        payload = Data(
            "{\"schema\":\"macos_ax_focus_window/v0\",\"status\":\"error\",\"error\":\"json_serialization_failed\"}"
                .utf8
        )
    }
    FileHandle.standardOutput.write(payload)
    FileHandle.standardOutput.write(Data("\n".utf8))
}

private func blockedReceipt(
    _ receipt: inout [String: Any],
    reasons: [String],
    foregroundBefore: ForegroundIdentity?,
    foregroundAfter: ForegroundIdentity? = nil
) {
    let after = foregroundAfter ?? foregroundBefore
    let changed = !sameForeground(foregroundBefore, after)
    receipt["status"] = "blocked"
    receipt["precondition"] = [
        "met": false,
        "reason_codes": reasons,
    ]
    receipt["verification"] = [
        "verdict": "blocked",
        "reason_codes": reasons,
        "recover": [
            "safe_to_retry": true,
            "next": "reobserve_frontmost_surface",
        ],
    ]
    receipt["foreground"] = [
        "before": foregroundJSON(foregroundBefore),
        "after": foregroundJSON(after),
        "changed": changed,
        "restore_attempted": false,
        "restore_reason": changed
            ? "not_attempted_fail_closed_external_foreground_change"
            : "not_applicable_no_action",
    ]
}

private func run(_ options: Options) -> ([String: Any], Int32) {
    var receipt = baseReceipt(compact: options.compact)
    receipt["target"] = [
        "pid": Int(options.pid),
        "bundle_id": options.bundleID,
        "selector": selectorJSON(options),
        "matched_window": NSNull(),
    ] as [String: Any]

    let trusted = AXIsProcessTrusted()
    receipt["permission"] = [
        "ax_trusted": trusted,
        "method": "AXIsProcessTrusted",
        "prompted": false,
    ]
    guard trusted else {
        blockedReceipt(
            &receipt,
            reasons: ["accessibility_not_trusted"],
            foregroundBefore: foregroundIdentity()
        )
        return (receipt, 3)
    }

    let beforeForeground = foregroundIdentity()
    guard foregroundMatches(beforeForeground, options: options) else {
        blockedReceipt(
            &receipt,
            reasons: ["target_application_not_frontmost"],
            foregroundBefore: beforeForeground
        )
        return (receipt, 4)
    }

    let application = AXUIElementCreateApplication(options.pid)
    let before = sampleSurface(application)
    receipt["world_revision"] = [
        "before": before.revision,
        "after": NSNull(),
    ]
    receipt["foreground"] = [
        "before": foregroundJSON(before.foreground),
        "after": NSNull(),
        "changed": false,
        "restore_attempted": false,
        "restore_reason": "not_needed_current_frontmost_scope",
    ]

    guard foregroundMatches(before.foreground, options: options) else {
        blockedReceipt(
            &receipt,
            reasons: ["foreground_changed_during_precondition"],
            foregroundBefore: beforeForeground,
            foregroundAfter: before.foreground
        )
        return (receipt, 5)
    }
    guard before.windowsError == .success else {
        receipt["status"] = "error"
        receipt["precondition"] = [
            "met": false,
            "reason_codes": ["window_enumeration_failed"],
        ]
        receipt["execution"] = [
            "attempted": false,
            "performed": false,
            "idempotent_noop": false,
            "primitive": NSNull(),
            "ax_error": axErrorJSON(stage: "read_windows", error: before.windowsError),
        ]
        receipt["verification"] = [
            "verdict": "error",
            "reason_codes": ["window_enumeration_failed"],
            "recover": ["safe_to_retry": true, "next": "reobserve_frontmost_surface"],
        ]
        return (receipt, 6)
    }

    let beforeSelector = assessSelector(before.windows, options: options)
    guard beforeSelector.hiddenCandidates.isEmpty else {
        receipt["target"] = [
            "pid": Int(options.pid),
            "bundle_id": options.bundleID,
            "selector": selectorJSON(options),
            "match_count": beforeSelector.matches.count,
            "hidden_candidate_count": beforeSelector.hiddenCandidates.count,
            "matched_window": NSNull(),
        ] as [String: Any]
        blockedReceipt(
            &receipt,
            reasons: ["selector_attributes_incomplete_hidden_candidate"],
            foregroundBefore: before.foreground
        )
        receipt["world_revision"] = ["before": before.revision, "after": before.revision]
        return (receipt, 7)
    }
    let matches = beforeSelector.matches
    guard matches.count == 1, let target = matches.first else {
        let reason = matches.isEmpty ? "exact_target_not_found" : "exact_target_ambiguous"
        receipt["target"] = [
            "pid": Int(options.pid),
            "bundle_id": options.bundleID,
            "selector": selectorJSON(options),
            "match_count": matches.count,
            "hidden_candidate_count": 0,
            "matched_window": NSNull(),
        ] as [String: Any]
        blockedReceipt(
            &receipt,
            reasons: [reason],
            foregroundBefore: before.foreground
        )
        receipt["world_revision"] = ["before": before.revision, "after": before.revision]
        return (receipt, 7)
    }

    receipt["target"] = [
        "pid": Int(options.pid),
        "bundle_id": options.bundleID,
        "selector": selectorJSON(options),
        "match_count": 1,
        "hidden_candidate_count": 0,
        "matched_window": windowJSON(target),
    ] as [String: Any]
    receipt["precondition"] = [
        "met": true,
        "reason_codes": [String](),
        "frontmost_target_match": true,
        "selector_unique": true,
        "selector_attributes_complete": true,
        "hidden_candidate_count": 0,
        "window_count": before.windows.count,
    ]

    // Re-sample the complete AX window surface immediately before the only
    // allowed mutation. Foreground identity alone is insufficient: a window
    // can disappear, change corroborators, or gain a duplicate AXIdentifier
    // between the initial observation and the setter.
    let immediatelyBeforeMutation = sampleSurface(application)
    guard foregroundMatches(immediatelyBeforeMutation.foreground, options: options) else {
        blockedReceipt(
            &receipt,
            reasons: ["foreground_changed_before_focus"],
            foregroundBefore: before.foreground,
            foregroundAfter: immediatelyBeforeMutation.foreground
        )
        receipt["world_revision"] = [
            "before": before.revision,
            "after": immediatelyBeforeMutation.revision,
        ]
        return (receipt, 8)
    }
    guard immediatelyBeforeMutation.windowsError == .success else {
        blockedReceipt(
            &receipt,
            reasons: ["window_enumeration_failed_before_focus"],
            foregroundBefore: before.foreground,
            foregroundAfter: immediatelyBeforeMutation.foreground
        )
        receipt["world_revision"] = [
            "before": before.revision,
            "after": immediatelyBeforeMutation.revision,
        ]
        return (receipt, 8)
    }
    let mutationSelector = assessSelector(
        immediatelyBeforeMutation.windows,
        options: options
    )
    guard mutationSelector.hiddenCandidates.isEmpty else {
        blockedReceipt(
            &receipt,
            reasons: ["selector_attributes_incomplete_hidden_candidate_before_focus"],
            foregroundBefore: before.foreground,
            foregroundAfter: immediatelyBeforeMutation.foreground
        )
        receipt["target"] = [
            "pid": Int(options.pid),
            "bundle_id": options.bundleID,
            "selector": selectorJSON(options),
            "match_count": mutationSelector.matches.count,
            "hidden_candidate_count": mutationSelector.hiddenCandidates.count,
            "matched_window": NSNull(),
        ] as [String: Any]
        receipt["world_revision"] = [
            "before": before.revision,
            "after": immediatelyBeforeMutation.revision,
        ]
        return (receipt, 8)
    }
    let mutationMatches = mutationSelector.matches
    guard mutationMatches.count == 1,
          let targetAtMutation = mutationMatches.first,
          CFEqual(targetAtMutation.element, target.element)
    else {
        let reason = mutationMatches.count > 1
            ? "exact_target_ambiguous_before_focus"
            : "exact_target_changed_before_focus"
        blockedReceipt(
            &receipt,
            reasons: [reason],
            foregroundBefore: before.foreground,
            foregroundAfter: immediatelyBeforeMutation.foreground
        )
        receipt["target"] = [
            "pid": Int(options.pid),
            "bundle_id": options.bundleID,
            "selector": selectorJSON(options),
            "match_count": mutationMatches.count,
            "hidden_candidate_count": 0,
            "matched_window": NSNull(),
        ] as [String: Any]
        receipt["world_revision"] = [
            "before": before.revision,
            "after": immediatelyBeforeMutation.revision,
        ]
        return (receipt, 8)
    }
    receipt["target"] = [
        "pid": Int(options.pid),
        "bundle_id": options.bundleID,
        "selector": selectorJSON(options),
        "match_count": 1,
        "hidden_candidate_count": 0,
        "matched_window": windowJSON(targetAtMutation),
    ] as [String: Any]
    receipt["precondition"] = [
        "met": true,
        "reason_codes": [String](),
        "frontmost_target_match": true,
        "selector_unique": true,
        "selector_attributes_complete": true,
        "hidden_candidate_count": 0,
        "window_count": immediatelyBeforeMutation.windows.count,
        "initial_world_revision": before.revision,
        "mutation_world_revision": immediatelyBeforeMutation.revision,
    ]
    receipt["world_revision"] = [
        "before": immediatelyBeforeMutation.revision,
        "after": NSNull(),
    ]

    var attempted = false
    var performed = false
    var idempotentNoop = false
    var primitive: String? = nil
    var executionError: [String: Any]? = nil

    if immediatelyBeforeMutation.focusedWindowError == .success,
       elementsEqual(immediatelyBeforeMutation.focusedWindow, targetAtMutation.element)
    {
        idempotentNoop = true
        primitive = "none_already_focused"
    } else {
        var focusedWindowSettable: DarwinBoolean = false
        let settableError = AXUIElementIsAttributeSettable(
            application,
            kAXFocusedWindowAttribute as CFString,
            &focusedWindowSettable
        )
        if settableError == .success, focusedWindowSettable.boolValue {
            attempted = true
            primitive = "AXFocusedWindow"
            let setError = AXUIElementSetAttributeValue(
                application,
                kAXFocusedWindowAttribute as CFString,
                targetAtMutation.element
            )
            if setError == .success {
                performed = true
            } else {
                executionError = axErrorJSON(stage: "set_focused_window", error: setError)
            }
        } else if (settableError == .success && !focusedWindowSettable.boolValue)
            || settableError == .attributeUnsupported
            || settableError == .notImplemented
        {
            var mainSettable: DarwinBoolean = false
            let mainSettableError = AXUIElementIsAttributeSettable(
                targetAtMutation.element,
                kAXMainAttribute as CFString,
                &mainSettable
            )
            if mainSettableError == .success, mainSettable.boolValue {
                attempted = true
                primitive = "AXMain_fallback"
                let setError = AXUIElementSetAttributeValue(
                    targetAtMutation.element,
                    kAXMainAttribute as CFString,
                    kCFBooleanTrue
                )
                if setError == .success {
                    performed = true
                } else {
                    executionError = axErrorJSON(stage: "set_main_fallback", error: setError)
                }
            } else {
                executionError = axErrorJSON(
                    stage: "query_main_fallback_settable",
                    error: mainSettableError == .success ? .attributeUnsupported : mainSettableError
                )
            }
        } else {
            executionError = axErrorJSON(
                stage: "query_focused_window_settable",
                error: settableError
            )
        }
    }

    receipt["execution"] = [
        "attempted": attempted,
        "performed": performed,
        "idempotent_noop": idempotentNoop,
        "primitive": nullIfNil(primitive),
        "ax_error": nullIfNil(executionError),
    ]

    if let executionError {
        let afterForeground = foregroundIdentity()
        let scopeStable = foregroundMatches(afterForeground, options: options)
            && sameForeground(immediatelyBeforeMutation.foreground, afterForeground)
        let changed = !scopeStable
        if attempted {
            receipt["execution"] = [
                "attempted": true,
                "performed": NSNull(),
                "idempotent_noop": false,
                "primitive": nullIfNil(primitive),
                "ax_error": executionError,
            ]
            receipt["status"] = "outcome_unknown"
            var reasons = [
                "focus_primitive_ax_error_after_dispatch",
                "postcondition_not_read_back",
            ]
            if !scopeStable {
                reasons.append("foreground_changed_after_dispatch")
            }
            receipt["postcondition"] = [
                "met": false,
                "exact_target_focused": false,
                "target_still_exact": false,
                "foreground_unchanged": scopeStable,
                "windows_read_ok": false,
                "focused_window_read_ok": false,
                "scope_stable": scopeStable,
                "hidden_candidate_count": 0,
                "observed_window": NSNull(),
            ]
            receipt["verification"] = [
                "verdict": "unknown",
                "reason_codes": reasons,
                "recover": [
                    "safe_to_retry": false,
                    "next": "reobserve_frontmost_surface",
                ],
            ]
            receipt["foreground"] = [
                "before": foregroundJSON(immediatelyBeforeMutation.foreground),
                "after": foregroundJSON(afterForeground),
                "changed": changed,
                "restore_attempted": false,
                "restore_reason": changed
                    ? "not_attempted_fail_closed_external_foreground_change"
                    : "not_needed_same_frontmost_application",
            ]
            return (receipt, 11)
        }

        receipt["status"] = "error"
        receipt["postcondition"] = [
            "met": false,
            "exact_target_focused": false,
            "target_still_exact": false,
            "foreground_unchanged": scopeStable,
            "windows_read_ok": false,
            "focused_window_read_ok": false,
            "scope_stable": scopeStable,
            "hidden_candidate_count": 0,
            "observed_window": NSNull(),
        ]
        receipt["verification"] = [
            "verdict": "error",
            "reason_codes": ["focus_primitive_failed"],
            "recover": [
                "safe_to_retry": false,
                "next": "reobserve_and_inspect_ax_error",
            ],
        ]
        receipt["foreground"] = [
            "before": foregroundJSON(immediatelyBeforeMutation.foreground),
            "after": foregroundJSON(afterForeground),
            "changed": changed,
            "restore_attempted": false,
            "restore_reason": changed
                ? "not_attempted_fail_closed_external_foreground_change"
                : "not_needed_same_frontmost_application",
        ]
        return (receipt, 9)
    }

    let deadline = DispatchTime.now().uptimeNanoseconds
        + UInt64(options.verifyTimeoutMs) * 1_000_000
    var after = sampleSurface(application)
    var postflight = assessPostflight(
        after,
        original: targetAtMutation,
        options: options,
        baselineForeground: immediatelyBeforeMutation.foreground
    )

    while true {
        if postflight.verified {
            break
        }
        if !postflight.scopeStable || DispatchTime.now().uptimeNanoseconds >= deadline {
            break
        }
        usleep(25_000)
        after = sampleSurface(application)
        postflight = assessPostflight(
            after,
            original: targetAtMutation,
            options: options,
            baselineForeground: immediatelyBeforeMutation.foreground
        )
    }

    let verified = postflight.verified
    let outcomeUnknown = !verified && !postflight.readbackComplete
    var reasonCodes = [String]()
    if !postflight.scopeStable {
        reasonCodes.append("foreground_changed_during_verification")
    }
    if after.windowsError != .success {
        reasonCodes.append("post_window_enumeration_failed")
    } else if postflight.hiddenCandidateCount > 0 {
        reasonCodes.append("post_selector_attributes_incomplete_hidden_candidate")
    }
    if after.focusedWindowError != .success {
        reasonCodes.append("focused_window_unreadable")
    }
    if postflight.readbackComplete && !verified {
        if !postflight.targetStillExact {
            reasonCodes.append("target_no_longer_exact")
        } else if !postflight.exactTargetFocused {
            reasonCodes.append("exact_target_not_focused")
        }
    }
    if reasonCodes.isEmpty && outcomeUnknown {
        reasonCodes.append("postcondition_readback_incomplete")
    } else if reasonCodes.isEmpty && !verified {
        reasonCodes.append("verification_timeout")
    }

    if idempotentNoop && !verified {
        idempotentNoop = false
        primitive = outcomeUnknown
            ? "none_initially_focused_postcondition_unknown"
            : "none_initially_focused_postcondition_lost"
        receipt["execution"] = [
            "attempted": false,
            "performed": false,
            "idempotent_noop": false,
            "primitive": nullIfNil(primitive),
            "ax_error": NSNull(),
        ]
    }
    let status = verified
        ? "verified"
        : (outcomeUnknown ? "outcome_unknown" : "verification_failed")
    let verdict = verified ? "verified" : (outcomeUnknown ? "unknown" : "failed")
    receipt["postcondition"] = [
        "met": verified,
        "exact_target_focused": postflight.exactTargetFocused,
        "target_still_exact": postflight.targetStillExact,
        "foreground_unchanged": postflight.scopeStable,
        "windows_read_ok": postflight.windowsReadOK,
        "focused_window_read_ok": postflight.focusedWindowReadOK,
        "scope_stable": postflight.scopeStable,
        "hidden_candidate_count": postflight.hiddenCandidateCount,
        "observed_window": windowJSON(postflight.currentTarget),
    ]
    receipt["status"] = status
    receipt["verification"] = [
        "verdict": verdict,
        "reason_codes": reasonCodes,
        "recover": [
            "safe_to_retry": !verified && !outcomeUnknown,
            "next": verified ? "none" : "reobserve_frontmost_surface",
        ],
    ]
    receipt["world_revision"] = [
        "before": immediatelyBeforeMutation.revision,
        "after": after.revision,
    ]
    receipt["foreground"] = [
        "before": foregroundJSON(immediatelyBeforeMutation.foreground),
        "after": foregroundJSON(after.foreground),
        "changed": !postflight.scopeStable,
        "restore_attempted": false,
        "restore_reason": postflight.scopeStable
            ? "not_needed_same_frontmost_application"
            : "not_attempted_fail_closed_external_foreground_change",
    ]
    return (receipt, verified ? 0 : (outcomeUnknown ? 11 : 10))
}

private func main() -> Int32 {
    let rawArguments = Array(CommandLine.arguments.dropFirst())
    let compactOnError = rawArguments.contains("--compact")
    do {
        let options = try parseOptions(rawArguments)
        let (receipt, exitCode) = run(options)
        emit(receipt, compact: options.compact)
        return exitCode
    } catch let error as CLIError {
        var receipt = baseReceipt(compact: compactOnError)
        receipt["status"] = "error"
        receipt["precondition"] = [
            "met": false,
            "reason_codes": ["invalid_arguments"],
        ]
        receipt["verification"] = [
            "verdict": "error",
            "reason_codes": ["invalid_arguments"],
            "recover": [
                "safe_to_retry": true,
                "next": "correct_arguments",
                "detail": error.description,
            ],
        ]
        emit(receipt, compact: compactOnError)
        return 2
    } catch {
        var receipt = baseReceipt(compact: compactOnError)
        receipt["status"] = "error"
        receipt["verification"] = [
            "verdict": "error",
            "reason_codes": ["unexpected_error"],
            "recover": [
                "safe_to_retry": false,
                "next": "inspect_receipt",
                "detail": String(describing: error),
            ],
        ]
        emit(receipt, compact: compactOnError)
        return 70
    }
}

exit(main())
