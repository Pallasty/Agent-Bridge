#!/usr/bin/env swift

import AppKit
import ApplicationServices
import Foundation

private let schema = "macos_ax_probe/v0"

private struct Options {
    let maxWindows: Int
    let includeWindows: Bool
}

private struct CLIError: Error, CustomStringConvertible {
    let description: String
}

private func parseOptions(_ arguments: [String]) throws -> Options {
    var maxWindows = 8
    var includeWindows = true
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
        if option == "--no-windows" {
            guard seen.insert(option).inserted else {
                throw CLIError(description: "duplicate_option:\(option)")
            }
            includeWindows = false
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
    return Options(maxWindows: maxWindows, includeWindows: includeWindows)
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

private struct WindowObservation {
    let index: Int
    let identifier: String?
    let title: String?
    let role: String?
    let subrole: String?
    let focused: Bool?
    let rect: [String: Double]?
    let titleReadOK: Bool
    let roleReadOK: Bool
    let focusedReadOK: Bool
}

private func rectAttribute(_ element: AXUIElement) -> [String: Double]? {
    let (positionValue, positionError) = copyAttribute(
        element,
        kAXPositionAttribute as CFString
    )
    let (sizeValue, sizeError) = copyAttribute(
        element,
        kAXSizeAttribute as CFString
    )
    guard positionError == .success,
          sizeError == .success,
          let positionValue,
          let sizeValue,
          CFGetTypeID(positionValue) == AXValueGetTypeID(),
          CFGetTypeID(sizeValue) == AXValueGetTypeID()
    else {
        return nil
    }
    var point = CGPoint.zero
    var size = CGSize.zero
    guard AXValueGetValue(positionValue as! AXValue, .cgPoint, &point),
          AXValueGetValue(sizeValue as! AXValue, .cgSize, &size)
    else {
        return nil
    }
    return [
        "x": Double(point.x),
        "y": Double(point.y),
        "width": Double(size.width),
        "height": Double(size.height),
    ]
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
    let sampleID = UUID().uuidString.lowercased()
    let capturedAt = Int(Date().timeIntervalSince1970)
    let trusted = AXIsProcessTrusted()
    var errors: [[String: Any]] = []
    var frontmostJSON: Any = NSNull()
    var windowsJSON: [[String: Any]] = []
    var sourceWindowCount: Int? = nil
    var windowsReadOK: Bool? = nil

    if trusted, options.includeWindows, let frontmost = NSWorkspace.shared.frontmostApplication {
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
            var observations: [WindowObservation] = []
            for (index, window) in windows.prefix(options.maxWindows).enumerated() {
                let (rawIdentifier, _) = stringAttribute(
                    window,
                    kAXIdentifierAttribute as CFString
                )
                let identifier = rawIdentifier?.trimmingCharacters(
                    in: .whitespacesAndNewlines
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
                observations.append(WindowObservation(
                    index: index,
                    identifier: identifier?.isEmpty == false ? identifier : nil,
                    title: title,
                    role: role,
                    subrole: subrole,
                    focused: focused,
                    rect: rectAttribute(window),
                    titleReadOK: titleOK,
                    roleReadOK: roleOK,
                    focusedReadOK: focusedOK
                ))
            }
            var identifierCounts: [String: Int] = [:]
            for observation in observations {
                if let identifier = observation.identifier {
                    identifierCounts[identifier, default: 0] += 1
                }
            }
            for observation in observations {
                let identity: [String: Any]
                let stableIdentityAvailable: Bool
                if let identifier = observation.identifier,
                   identifierCounts[identifier] == 1 {
                    identity = [
                        "kind": "ax_identifier",
                        "value": identifier,
                        "unique_in_sample": true,
                        "stable_across_samples": true,
                    ]
                    stableIdentityAvailable = true
                } else if let identifier = observation.identifier {
                    identity = [
                        "kind": "ambiguous_ax_identifier",
                        "value": identifier,
                        "unique_in_sample": false,
                        "stable_across_samples": false,
                    ]
                    stableIdentityAvailable = false
                } else {
                    identity = [
                        "kind": "sample_index",
                        "value": String(observation.index),
                        "unique_in_sample": false,
                        "stable_across_samples": false,
                    ]
                    stableIdentityAvailable = false
                }
                windowsJSON.append([
                    "index": observation.index,
                    "ax_identifier": nullIfNil(observation.identifier),
                    "title": nullIfNil(observation.title),
                    "role": nullIfNil(observation.role),
                    "subrole": nullIfNil(observation.subrole),
                    "focused": nullIfNil(observation.focused),
                    "position": nullIfNil(observation.rect.map {
                        [$0["x"]!, $0["y"]!]
                    }),
                    "size": nullIfNil(observation.rect.map {
                        [$0["width"]!, $0["height"]!]
                    }),
                    "rect": nullIfNil(observation.rect),
                    "identity": identity,
                    "stable_identity_available": stableIdentityAvailable,
                    "action_eligible": stableIdentityAvailable,
                ])
                // AXIdentifier is optional in many real applications. Its
                // absence/duplication limits continuity and action admission,
                // but does not invalidate current-sample window semantics.
                if !observation.titleReadOK
                    || !observation.roleReadOK
                    || !observation.focusedReadOK {
                    errors.append([
                        "stage": "native_ax_window_attributes",
                        "index": observation.index,
                        "title_read_ok": observation.titleReadOK,
                        "role_read_ok": observation.roleReadOK,
                        "focused_read_ok": observation.focusedReadOK,
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
        let finalFrontmost = NSWorkspace.shared.frontmostApplication
        if finalFrontmost?.processIdentifier != pid {
            errors.append([
                "stage": "native_ax_frontmost_changed_during_sample",
                "initial_pid": Int(pid),
                "final_pid": nullIfNil(finalFrontmost.map { Int($0.processIdentifier) }),
                "initial_bundle_id": nullIfNil(frontmost.bundleIdentifier),
                "final_bundle_id": nullIfNil(finalFrontmost?.bundleIdentifier),
            ])
        }
    } else if !trusted {
        errors.append(["stage": "ax_trust"])
    } else if options.includeWindows {
        errors.append(["stage": "frontmost_application"])
    }

    let frontmost = frontmostJSON as? [String: Any]
    let pid = frontmost?["pid"] as? Int
    let appName = frontmost?["name"] as? String
    let bundleID = frontmost?["bundle_id"] as? String
    let appIdentityValid = pid.map { $0 > 0 } == true
        && (
            appName.map { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } == true
                || bundleID.map { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } == true
        )
    let countsConsistent = sourceWindowCount == windowsJSON.count
    let truncated = sourceWindowCount.map { $0 > windowsJSON.count } ?? false
    var incompleteReasons: [String] = []
    let coverageComplete: Bool
    if options.includeWindows {
        if !trusted
            || !appIdentityValid
            || windowsReadOK != true
            || sourceWindowCount.map({ $0 >= windowsJSON.count }) != true
            || !errors.isEmpty {
            incompleteReasons.append("probe_not_ready")
        }
        if !appIdentityValid { incompleteReasons.append("frontmost_app_identity_invalid") }
        if windowsReadOK != true { incompleteReasons.append("window_enumeration_unconfirmed") }
        if !countsConsistent { incompleteReasons.append("window_counts_incomplete") }
        if truncated { incompleteReasons.append("window_enumeration_truncated") }
        if !errors.isEmpty { incompleteReasons.append("probe_errors") }
        coverageComplete = incompleteReasons.isEmpty
    } else {
        coverageComplete = trusted && errors.isEmpty
        if !coverageComplete { incompleteReasons.append("ax_trust_incomplete") }
    }
    let statusReady: Bool
    if options.includeWindows {
        statusReady = trusted
            && appIdentityValid
            && windowsReadOK == true
            && sourceWindowCount.map { $0 >= windowsJSON.count } == true
            && errors.isEmpty
    } else {
        statusReady = coverageComplete
    }
    let status = statusReady ? "ready" : "degraded"
    for index in windowsJSON.indices {
        let stable = windowsJSON[index]["stable_identity_available"] as? Bool == true
        windowsJSON[index]["action_eligible"] = coverageComplete && stable
    }
    let stableCount = windowsJSON.filter {
        ($0["stable_identity_available"] as? Bool) == true
    }.count
    let ambiguousCount = windowsJSON.filter {
        (($0["identity"] as? [String: Any])?["kind"] as? String)
            == "ambiguous_ax_identifier"
    }.count
    let sampleLocalCount = windowsJSON.filter {
        (($0["identity"] as? [String: Any])?["kind"] as? String)
            == "sample_index"
    }.count
    let actionEligibleCount = windowsJSON.filter {
        ($0["action_eligible"] as? Bool) == true
    }.count
    let elapsedMs = max(0, Int(Date().timeIntervalSince(started) * 1000.0))
    emit([
        "schema": schema,
        "sample_id": sampleID,
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
        "sample_observation_complete": coverageComplete,
        "incomplete_reasons": incompleteReasons,
        "identity_coverage": [
            "stable_ax_identifier_count": stableCount,
            "ambiguous_ax_identifier_count": ambiguousCount,
            "sample_local_index_count": sampleLocalCount,
            "stable_identity_available": stableCount > 0,
            "action_eligible_window_count": actionEligibleCount,
        ],
        "stable_identity_available": stableCount > 0,
        "action_eligible": coverageComplete && stableCount > 0,
        "limits": [
            "max_windows": options.maxWindows,
            "truncated": truncated,
            "include_windows": options.includeWindows,
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
        "sample_id": UUID().uuidString.lowercased(),
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
        "sample_observation_complete": false,
        "incomplete_reasons": ["probe_not_ready", "input_invalid"],
        "identity_coverage": [
            "stable_ax_identifier_count": 0,
            "ambiguous_ax_identifier_count": 0,
            "sample_local_index_count": 0,
            "stable_identity_available": false,
            "action_eligible_window_count": 0,
        ],
        "stable_identity_available": false,
        "action_eligible": false,
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
