#!/usr/bin/env swift

import AppKit
import ApplicationServices
import Foundation

private let schema = "macos_ax_probe/v0"

private struct Options {
    let maxWindows: Int
}

private struct CLIError: Error, CustomStringConvertible {
    let description: String
}

private func parseOptions(_ arguments: [String]) throws -> Options {
    var maxWindows = 8
    var seen = Set<String>()
    var cursor = 0
    while cursor < arguments.count {
        let option = arguments[cursor]
        if option == "--compact" {
            guard seen.insert(option).inserted else {
                throw CLIError(description: "duplicate_option:\(option)")
            }
            cursor += 1
            continue
        }
        guard option == "--max-windows" else {
            throw CLIError(description: "unknown_option:\(option)")
        }
        guard seen.insert(option).inserted else {
            throw CLIError(description: "duplicate_option:\(option)")
        }
        guard cursor + 1 < arguments.count,
              let parsed = Int(arguments[cursor + 1]),
              (0 ... 50).contains(parsed)
        else {
            throw CLIError(description: "invalid_max_windows:must_be_0_through_50")
        }
        maxWindows = parsed
        cursor += 2
    }
    return Options(maxWindows: maxWindows)
}

private func nullIfNil(_ value: Any?) -> Any {
    value ?? NSNull()
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
) -> (String?, Bool) {
    let (value, error) = copyAttribute(element, attribute)
    guard error == .success, let string = value as? String else {
        return (nil, false)
    }
    return (string, true)
}

private func boolAttribute(
    _ element: AXUIElement,
    _ attribute: CFString
) -> (Bool?, Bool) {
    let (value, error) = copyAttribute(element, attribute)
    guard error == .success, let number = value as? NSNumber else {
        return (nil, false)
    }
    return (number.boolValue, true)
}

private func emit(_ payload: [String: Any], exitCode: Int32) -> Never {
    let data: Data
    do {
        data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    } catch {
        FileHandle.standardOutput.write(
            Data("{\"schema\":\"macos_ax_probe/v0\",\"status\":\"degraded\",\"read_only\":true,\"errors\":[{\"stage\":\"serialization\"}]}\n".utf8)
        )
        Foundation.exit(3)
    }
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
    Foundation.exit(exitCode)
}

private func platformMachine() -> String {
    var systemInfo = utsname()
    guard uname(&systemInfo) == 0 else { return "unknown" }
    return withUnsafePointer(to: &systemInfo.machine) {
        $0.withMemoryRebound(to: CChar.self, capacity: 1) {
            String(cString: $0)
        }
    }
}

private func run() throws -> Never {
    let options = try parseOptions(Array(CommandLine.arguments.dropFirst()))
    let started = Date()
    let capturedAt = Int(Date().timeIntervalSince1970)
    let trusted = AXIsProcessTrusted()
    var errors: [[String: Any]] = []
    var frontmostJSON: Any = NSNull()
    var windowsJSON: [[String: Any]] = []
    var sourceWindowCount: Int? = nil
    var windowsReadOK: Bool? = nil

    if trusted, let frontmost = NSWorkspace.shared.frontmostApplication {
        let pid = frontmost.processIdentifier
        frontmostJSON = [
            "name": nullIfNil(frontmost.localizedName),
            "pid": Int(pid),
            "bundle_id": nullIfNil(frontmost.bundleIdentifier),
            "role": "AXApplication",
        ] as [String: Any]
        let application = AXUIElementCreateApplication(pid)
        let (rawWindows, windowsError) = copyAttribute(
            application,
            kAXWindowsAttribute as CFString
        )
        if windowsError == .success, let windows = rawWindows as? [AXUIElement] {
            windowsReadOK = true
            sourceWindowCount = windows.count
            for (index, window) in windows.prefix(options.maxWindows).enumerated() {
                let (identifier, identifierOK) = stringAttribute(
                    window,
                    kAXIdentifierAttribute as CFString
                )
                let (title, titleOK) = stringAttribute(
                    window,
                    kAXTitleAttribute as CFString
                )
                let (role, roleOK) = stringAttribute(
                    window,
                    kAXRoleAttribute as CFString
                )
                let (subrole, _) = stringAttribute(
                    window,
                    kAXSubroleAttribute as CFString
                )
                let (focused, focusedOK) = boolAttribute(
                    window,
                    kAXFocusedAttribute as CFString
                )
                let identity: [String: Any]
                if identifierOK, let identifier, !identifier.isEmpty {
                    identity = [
                        "kind": "ax_identifier",
                        "value": identifier,
                        "stable_across_samples": true,
                    ]
                } else {
                    identity = [
                        "kind": "sample_index",
                        "value": String(index),
                        "stable_across_samples": false,
                    ]
                }
                windowsJSON.append([
                    "index": index,
                    "ax_identifier": nullIfNil(identifier),
                    "title": nullIfNil(title),
                    "role": nullIfNil(role),
                    "subrole": nullIfNil(subrole),
                    "focused": nullIfNil(focused),
                    "rect": NSNull(),
                    "identity": identity,
                ])
                if !identifierOK || !titleOK || !roleOK || !focusedOK {
                    errors.append([
                        "stage": "native_ax_window_attributes",
                        "index": index,
                        "ax_identifier_read_ok": identifierOK,
                        "title_read_ok": titleOK,
                        "role_read_ok": roleOK,
                        "focused_read_ok": focusedOK,
                    ])
                }
            }
        } else {
            windowsReadOK = false
            errors.append([
                "stage": "native_ax_windows",
                "ax_error": Int(windowsError.rawValue),
            ])
        }
    } else if !trusted {
        errors.append(["stage": "ax_trust"])
    } else {
        errors.append(["stage": "frontmost_application"])
    }

    let frontmost = frontmostJSON as? [String: Any]
    let pid = frontmost?["pid"] as? Int
    let bundleID = frontmost?["bundle_id"] as? String
    let appIdentityValid = pid.map { $0 > 0 } == true
        && bundleID.map { !$0.isEmpty } == true
    let countsConsistent = sourceWindowCount == windowsJSON.count
    let truncated = sourceWindowCount.map { $0 > windowsJSON.count } ?? false
    var incompleteReasons: [String] = []
    if !trusted || !appIdentityValid || windowsReadOK != true || !countsConsistent || truncated || !errors.isEmpty {
        incompleteReasons.append("probe_not_ready")
    }
    if !appIdentityValid { incompleteReasons.append("frontmost_app_identity_invalid") }
    if windowsReadOK != true { incompleteReasons.append("window_enumeration_unconfirmed") }
    if !countsConsistent { incompleteReasons.append("window_counts_incomplete") }
    if truncated { incompleteReasons.append("window_enumeration_truncated") }
    if !errors.isEmpty { incompleteReasons.append("probe_errors") }
    let coverageComplete = incompleteReasons.isEmpty
    let status = coverageComplete ? "ready" : "degraded"
    let elapsedMs = max(0, Int(Date().timeIntervalSince(started) * 1000.0))
    emit([
        "schema": schema,
        "captured_at": capturedAt,
        "platform": [
            "system": "Darwin",
            "release": ProcessInfo.processInfo.operatingSystemVersionString,
            "machine": platformMachine(),
        ],
        "read_only": true,
        "status": status,
        "permission": [
            "ax_trusted": trusted,
            "method": "AXIsProcessTrusted",
            "prompted": false,
        ],
        "frontmost_app": frontmostJSON,
        "windows": windowsJSON,
        "window_count": windowsJSON.count,
        "source_window_count": nullIfNil(sourceWindowCount),
        "windows_read_ok": nullIfNil(windowsReadOK),
        "app_identity_valid": appIdentityValid,
        "counts_consistent": countsConsistent,
        "coverage_complete": coverageComplete,
        "incomplete_reasons": incompleteReasons,
        "limits": [
            "max_windows": options.maxWindows,
            "truncated": truncated,
            "include_windows": true,
        ],
        "errors": errors,
        "elapsed_ms": elapsedMs,
        "source": [
            "adapter": "native_ax",
            "uses_system_events": false,
            "uses_apple_events": false,
        ],
    ], exitCode: 0)
}

do {
    try run()
} catch {
    emit([
        "schema": schema,
        "captured_at": Int(Date().timeIntervalSince1970),
        "platform": ["system": "Darwin"],
        "read_only": true,
        "status": "degraded",
        "permission": [
            "ax_trusted": AXIsProcessTrusted(),
            "method": "AXIsProcessTrusted",
            "prompted": false,
        ],
        "frontmost_app": NSNull(),
        "windows": [],
        "window_count": 0,
        "source_window_count": NSNull(),
        "windows_read_ok": NSNull(),
        "app_identity_valid": false,
        "counts_consistent": false,
        "coverage_complete": false,
        "incomplete_reasons": ["probe_not_ready", "input_invalid"],
        "limits": ["max_windows": 0, "truncated": false, "include_windows": true],
        "errors": [["stage": "input", "message": String(describing: error)]],
        "elapsed_ms": 0,
        "source": [
            "adapter": "native_ax",
            "uses_system_events": false,
            "uses_apple_events": false,
        ],
    ], exitCode: 2)
}
