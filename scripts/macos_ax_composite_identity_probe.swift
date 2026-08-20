#!/usr/bin/env swift

import AppKit
import ApplicationServices
import CoreGraphics
import Darwin
import Foundation

private let schema = "agent_bridge.macos_ax_composite_identity_probe.v0"

private struct Options { let maxWindows: Int; let intervalMs: Int }
private struct CLIError: Error, CustomStringConvertible { let description: String }
private struct Rect: Equatable { let x: Double; let y: Double; let width: Double; let height: Double }
private struct AXWindow { let index: Int; let title: String; let role: String; let focused: Bool; let rect: Rect }
private struct CGWindow { let id: UInt32; let title: String; let rect: Rect }
private struct Match { let ax: AXWindow; let cg: CGWindow }
private struct Sample { let bundleID: String; let pid: pid_t; let launchedAtMs: Int64; let matches: [Match]; let axCount: Int; let cgCount: Int }

private func parseOptions(_ arguments: [String]) throws -> Options {
    var maxWindows = 50
    var intervalMs = 250
    var seen = Set<String>()
    var cursor = 0
    while cursor < arguments.count {
        let option = arguments[cursor]
        if option == "--compact" {
            guard seen.insert(option).inserted else { throw CLIError(description: "duplicate_option:\(option)") }
            cursor += 1
            continue
        }
        guard option == "--max-windows" || option == "--interval-ms" else {
            throw CLIError(description: "unknown_option:\(option)")
        }
        guard seen.insert(option).inserted, cursor + 1 < arguments.count,
              let parsed = Int(arguments[cursor + 1]) else {
            throw CLIError(description: "invalid_option:\(option)")
        }
        if option == "--max-windows" {
            guard (1 ... 50).contains(parsed) else { throw CLIError(description: "invalid_max_windows") }
            maxWindows = parsed
        } else {
            guard (100 ... 1000).contains(parsed) else { throw CLIError(description: "invalid_interval_ms") }
            intervalMs = parsed
        }
        cursor += 2
    }
    return Options(maxWindows: maxWindows, intervalMs: intervalMs)
}

private func copyAttribute(_ element: AXUIElement, _ attribute: CFString) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, attribute, &value) == .success ? value : nil
}

private func axRect(_ element: AXUIElement) -> Rect? {
    guard let position = copyAttribute(element, kAXPositionAttribute as CFString),
          let size = copyAttribute(element, kAXSizeAttribute as CFString),
          CFGetTypeID(position) == AXValueGetTypeID(),
          CFGetTypeID(size) == AXValueGetTypeID() else { return nil }
    var point = CGPoint.zero
    var dimensions = CGSize.zero
    guard AXValueGetValue(position as! AXValue, .cgPoint, &point),
          AXValueGetValue(size as! AXValue, .cgSize, &dimensions) else { return nil }
    return Rect(x: point.x, y: point.y, width: dimensions.width, height: dimensions.height)
}

private func near(_ left: Rect, _ right: Rect) -> Bool {
    abs(left.x - right.x) <= 1 && abs(left.y - right.y) <= 1
        && abs(left.width - right.width) <= 1 && abs(left.height - right.height) <= 1
}

private func processLaunchTimeMs(_ pid: pid_t) -> Int64? {
    var info = proc_bsdinfo()
    let expected = Int32(MemoryLayout<proc_bsdinfo>.size)
    let copied = withUnsafeMutablePointer(to: &info) {
        proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, $0, expected)
    }
    guard copied == expected, info.pbi_start_tvsec > 0 else { return nil }
    return Int64(info.pbi_start_tvsec) * 1000 + Int64(info.pbi_start_tvusec) / 1000
}

private func capture(maxWindows: Int) throws -> Sample {
    guard AXIsProcessTrusted() else { throw CLIError(description: "ax_not_trusted") }
    guard let app = NSWorkspace.shared.frontmostApplication,
          let bundleID = app.bundleIdentifier, !bundleID.isEmpty,
          let launchedAtMs = processLaunchTimeMs(app.processIdentifier) else {
        throw CLIError(description: "frontmost_identity_incomplete")
    }
    let pid = app.processIdentifier
    let application = AXUIElementCreateApplication(pid)
    guard let raw = copyAttribute(application, kAXWindowsAttribute as CFString) as? [AXUIElement],
          raw.count <= maxWindows else { throw CLIError(description: "ax_windows_incomplete_or_truncated") }
    var axWindows: [AXWindow] = []
    for (index, element) in raw.enumerated() {
        guard let title = copyAttribute(element, kAXTitleAttribute as CFString) as? String, !title.isEmpty else {
            throw CLIError(description: "ax_title_incomplete")
        }
        guard let role = copyAttribute(element, kAXRoleAttribute as CFString) as? String, !role.isEmpty else {
            throw CLIError(description: "ax_role_incomplete")
        }
        guard let focusedNumber = copyAttribute(element, kAXFocusedAttribute as CFString) as? NSNumber else {
            throw CLIError(description: "ax_focused_incomplete")
        }
        guard let rect = axRect(element) else { throw CLIError(description: "ax_rect_incomplete") }
        axWindows.append(AXWindow(index: index, title: title, role: role, focused: focusedNumber.boolValue, rect: rect))
    }
    guard let info = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else {
        throw CLIError(description: "cgwindow_read_failed")
    }
    var cgWindows: [CGWindow] = []
    for entry in info {
        guard (entry[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == pid,
              (entry[kCGWindowLayer as String] as? NSNumber)?.intValue == 0,
              let id = (entry[kCGWindowNumber as String] as? NSNumber)?.uint32Value,
              id > 0,
              let title = entry[kCGWindowName as String] as? String,
              !title.isEmpty,
              let bounds = entry[kCGWindowBounds as String] as? [String: Any],
              let x = (bounds["X"] as? NSNumber)?.doubleValue,
              let y = (bounds["Y"] as? NSNumber)?.doubleValue,
              let width = (bounds["Width"] as? NSNumber)?.doubleValue,
              let height = (bounds["Height"] as? NSNumber)?.doubleValue else { continue }
        cgWindows.append(CGWindow(id: id, title: title, rect: Rect(x: x, y: y, width: width, height: height)))
    }
    var matches: [Match] = []
    for ax in axWindows {
        let candidates = cgWindows.filter { $0.title == ax.title && near($0.rect, ax.rect) }
        guard candidates.count == 1 else { throw CLIError(description: "ax_to_cg_not_unique") }
        matches.append(Match(ax: ax, cg: candidates[0]))
    }
    guard Set(matches.map { $0.cg.id }).count == matches.count else {
        throw CLIError(description: "cg_to_ax_not_unique")
    }
    return Sample(bundleID: bundleID, pid: pid, launchedAtMs: launchedAtMs, matches: matches, axCount: axWindows.count, cgCount: cgWindows.count)
}

private func emit(_ payload: [String: Any], exitCode: Int32) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
    FileHandle.standardOutput.write(data); FileHandle.standardOutput.write(Data("\n".utf8)); Foundation.exit(exitCode)
}

private func run() throws -> Never {
    let options = try parseOptions(Array(CommandLine.arguments.dropFirst()))
    let first = try capture(maxWindows: options.maxWindows)
    Thread.sleep(forTimeInterval: Double(options.intervalMs) / 1000.0)
    let second = try capture(maxWindows: options.maxWindows)
    guard first.bundleID == second.bundleID, first.pid == second.pid, first.launchedAtMs == second.launchedAtMs else {
        throw CLIError(description: "frontmost_process_changed_between_samples")
    }
    let firstByID = Dictionary(uniqueKeysWithValues: first.matches.map { ($0.cg.id, $0) })
    let secondByID = Dictionary(uniqueKeysWithValues: second.matches.map { ($0.cg.id, $0) })
    guard Set(firstByID.keys) == Set(secondByID.keys) else { throw CLIError(description: "window_set_changed_between_samples") }
    let candidates: [[String: Any]] = firstByID.keys.sorted().map { id in
        let before = firstByID[id]!, after = secondByID[id]!
        return [
            "cg_window_id": Int(id), "role": before.ax.role,
            "focused_first": before.ax.focused, "focused_second": after.ax.focused,
            "unique_bijection_first": true, "unique_bijection_second": true,
            "stable_across_samples": before.ax.role == after.ax.role && near(before.ax.rect, after.ax.rect),
        ]
    }
    let eligible = candidates.count >= 2
        && candidates.allSatisfy { $0["stable_across_samples"] as? Bool == true }
        && candidates.contains { $0["focused_first"] as? Bool == false }
    emit([
        "schema": schema, "status": eligible ? "eligible" : "ineligible", "read_only": true,
        "captured_at": Int(Date().timeIntervalSince1970),
        "platform": ["system": "Darwin"],
        "permission": ["ax_trusted": true, "prompted": false],
        "scope": ["bundle_id": first.bundleID, "pid": Int(first.pid), "process_launch_time_ms": first.launchedAtMs],
        "sample_count": 2, "sample_interval_ms": options.intervalMs,
        "ax_window_count": first.axCount, "cg_window_count": first.cgCount,
        "candidates": candidates, "eligible_now": eligible,
        "correlation": ["title_used_only_for_matching": true, "bounds_used_only_for_matching": true, "tolerance_points": 1, "bidirectional_unique_required": true],
        "source": ["uses_ax_setters": false, "uses_system_events": false, "uses_apple_events": false, "uses_cgwindow_read_only": true],
        "action_performed": false,
    ], exitCode: eligible ? 0 : 2)
}

do { try run() } catch {
    emit(["schema": schema, "status": "ineligible", "read_only": true, "eligible_now": false,
          "reason": String(describing: error), "action_performed": false], exitCode: 2)
}
