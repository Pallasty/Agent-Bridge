//! Per-record **version vectors** for conflict-aware memory sync.
//!
//! Track MS · MS-1 (see `docs/design/MEMORY_SYNC_VERSION_VECTOR_BORROW_2026_05_24.md`).
//!
//! A faithful Rust port of Syncthing's `lib/protocol/vector.go` semantics,
//! adapted to agent-bridge's SQLite-as-truth model. The point is to move
//! conflict resolution **down from the git-branch layer** (the blunt
//! `reset --hard` fallback in `crates/bridge/src/sync.rs`) **to the
//! SQLite-record layer**: once every memory row carries a version vector,
//! jsonl import becomes a conflict-aware per-key merge and branch divergence
//! stops being a correctness event.
//!
//! ## Model
//!
//! A [`VersionVector`] is a sorted list of [`Counter`]s, one per **node**
//! (machine — `aio2` / `mac`), *not* per session. Every write on a node bumps
//! that node's counter via [`VersionVector::update`]. Comparing two vectors
//! ([`VersionVector::compare`]) yields an [`Ordering`]; the two `Concurrent*`
//! variants mean *both sides advanced independently* — i.e. a genuine
//! conflict that MS-2 will preserve non-destructively.
//!
//! The counter value is `max(previous + 1, wall_clock_unix)` — a Lamport
//! counter with a wall-clock floor. The floor keeps values monotonic *and*
//! comparable across the serial Mac↔aio2 handoff even when a clock is slightly
//! off, without ever letting a value go backwards.

use serde::{Deserialize, Serialize};
use std::fmt;
use std::time::{SystemTime, UNIX_EPOCH};

/// Stable identifier for a sync node (machine), e.g. `aio2` / `mac`.
///
/// Mirrors Syncthing's `ShortID` (a truncated device-cert hash). We derive it
/// from the node *name* with a dependency-free FNV-1a so the mapping is stable
/// and reproducible across machines. Never `0` for a non-empty name in
/// practice (FNV-1a of a non-empty string is overwhelmingly non-zero), and the
/// comparison logic treats a missing counter as value `0`, so a `0` id is
/// simply avoided by convention rather than relied upon.
pub type NodeId = u64;

/// Derive a stable [`NodeId`] from a node name via FNV-1a (64-bit).
///
/// Dependency-free and deterministic: the same name yields the same id on
/// every machine, which is the only property the version vector needs.
pub fn node_id_from_name(name: &str) -> NodeId {
    const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
    const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;
    let mut hash = FNV_OFFSET;
    for byte in name.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

/// A single per-node counter within a [`VersionVector`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Counter {
    pub id: NodeId,
    pub value: u64,
}

/// The relationship between two [`VersionVector`]s.
///
/// There is no true "concurrent greater"/"concurrent lesser" in version-vector
/// theory — only "concurrent". But returning a strict total order is useful for
/// stable sorts and deterministic tie-breaks, so (matching Syncthing) we split
/// the concurrent case by which side was seen to be greater first. Use
/// [`VersionVector::concurrent`] to collapse both back into "is this a
/// conflict?".
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Ordering {
    Equal,
    Greater,
    Lesser,
    ConcurrentLesser,
    ConcurrentGreater,
}

/// A version vector: a node→counter map kept sorted by [`NodeId`] ascending.
///
/// The zero value (`VersionVector::default()`) is a usable empty vector.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct VersionVector {
    /// Sorted by `id` ascending. Invariant maintained by every constructor and
    /// mutator in this module.
    pub counters: Vec<Counter>,
}

fn unix_secs_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

impl VersionVector {
    /// Return a vector with `id`'s counter incremented. The new value is
    /// `max(previous + 1, now)` — a Lamport bump with a wall-clock floor.
    #[must_use]
    pub fn update(self, id: NodeId) -> Self {
        self.update_with_now(id, unix_secs_now())
    }

    /// [`update`](Self::update) with an explicit `now` — for deterministic
    /// tests and replay.
    #[must_use]
    pub fn update_with_now(mut self, id: NodeId, now: u64) -> Self {
        for i in 0..self.counters.len() {
            if self.counters[i].id == id {
                // Existing counter: Lamport bump with wall-clock floor.
                self.counters[i].value = (self.counters[i].value + 1).max(now);
                return self;
            } else if self.counters[i].id > id {
                // Insert a fresh counter keeping the sort invariant.
                self.counters.insert(
                    i,
                    Counter {
                        id,
                        value: 1.max(now),
                    },
                );
                return self;
            }
        }
        // Append (largest id seen so far, or first counter).
        self.counters.push(Counter {
            id,
            value: 1.max(now),
        });
        self
    }

    /// Element-wise maximum of `self` and `other` — the clean-merge result
    /// when neither side is strictly behind. (When the two are
    /// [`concurrent`](Self::concurrent), merging silently picks the per-node
    /// maxima; callers that care about conflicts must check
    /// [`compare`](Self::compare) *before* merging.)
    #[must_use]
    pub fn merge(&self, other: &VersionVector) -> VersionVector {
        let (a, b) = (&self.counters, &other.counters);
        let mut out = Vec::with_capacity(a.len().max(b.len()));
        let (mut i, mut j) = (0usize, 0usize);
        while i < a.len() && j < b.len() {
            if a[i].id < b[j].id {
                out.push(a[i]);
                i += 1;
            } else if b[j].id < a[i].id {
                out.push(b[j]);
                j += 1;
            } else {
                out.push(Counter {
                    id: a[i].id,
                    value: a[i].value.max(b[j].value),
                });
                i += 1;
                j += 1;
            }
        }
        out.extend_from_slice(&a[i..]);
        out.extend_from_slice(&b[j..]);
        VersionVector { counters: out }
    }

    /// The [`Ordering`] describing `self`'s relation to `other`.
    ///
    /// Faithful port of Syncthing `Vector.Compare` (`vector.go:263`): a single
    /// merge-walk over the two sorted counter lists, where a counter present on
    /// one side and absent on the other is treated as value `0` on the absent
    /// side.
    #[must_use]
    pub fn compare(&self, other: &VersionVector) -> Ordering {
        let (a, b) = (&self.counters, &other.counters);
        let (mut ai, mut bi) = (0usize, 0usize);
        let mut result = Ordering::Equal;

        while ai < a.len() || bi < b.len() {
            let a_missing = ai >= a.len();
            let b_missing = bi >= b.len();
            let av = if a_missing { Counter { id: 0, value: 0 } } else { a[ai] };
            let bv = if b_missing { Counter { id: 0, value: 0 } } else { b[bi] };

            if !a_missing && !b_missing && av.id == bv.id {
                // Both sides have this counter.
                if av.value > bv.value {
                    if result == Ordering::Lesser {
                        return Ordering::ConcurrentLesser;
                    }
                    result = Ordering::Greater;
                } else if av.value < bv.value {
                    if result == Ordering::Greater {
                        return Ordering::ConcurrentGreater;
                    }
                    result = Ordering::Lesser;
                }
            } else if (!a_missing && av.id < bv.id) || b_missing {
                // Counter present on a, missing on b.
                if av.value > 0 {
                    if result == Ordering::Lesser {
                        return Ordering::ConcurrentLesser;
                    }
                    result = Ordering::Greater;
                }
            } else {
                // Counter present on b, missing on a.
                if bv.value > 0 {
                    if result == Ordering::Greater {
                        return Ordering::ConcurrentGreater;
                    }
                    result = Ordering::Lesser;
                }
            }

            if ai < a.len() && (b_missing || av.id <= bv.id) {
                ai += 1;
            }
            if bi < b.len() && (a_missing || bv.id <= av.id) {
                bi += 1;
            }
        }

        result
    }

    /// `true` when the two vectors are equivalent.
    #[must_use]
    pub fn equal(&self, other: &VersionVector) -> bool {
        self.compare(other) == Ordering::Equal
    }

    /// `true` when `self` is equal to or strictly behind `other`.
    #[must_use]
    pub fn lesser_equal(&self, other: &VersionVector) -> bool {
        matches!(self.compare(other), Ordering::Lesser | Ordering::Equal)
    }

    /// `true` when `self` is equal to or strictly ahead of `other`.
    #[must_use]
    pub fn greater_equal(&self, other: &VersionVector) -> bool {
        matches!(self.compare(other), Ordering::Greater | Ordering::Equal)
    }

    /// `true` when the two vectors are concurrent — i.e. a conflict: each side
    /// advanced a counter the other did not.
    #[must_use]
    pub fn concurrent(&self, other: &VersionVector) -> bool {
        matches!(
            self.compare(other),
            Ordering::ConcurrentLesser | Ordering::ConcurrentGreater
        )
    }

    /// Current value of `id`'s counter, or `0` if absent.
    #[must_use]
    pub fn counter(&self, id: NodeId) -> u64 {
        self.counters
            .iter()
            .find(|c| c.id == id)
            .map_or(0, |c| c.value)
    }

    /// `true` when there are no counters.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.counters.is_empty()
    }
}

/// Compact, round-trippable string form: `"<hexid>:<value>,<hexid>:<value>"`,
/// sorted by id (the storage form for a SQLite `TEXT` column). The empty
/// vector renders as `""`.
impl fmt::Display for VersionVector {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for (i, c) in self.counters.iter().enumerate() {
            if i > 0 {
                f.write_str(",")?;
            }
            write!(f, "{:x}:{}", c.id, c.value)?;
        }
        Ok(())
    }
}

/// Error parsing a [`VersionVector`] from its string form.
#[derive(Debug, thiserror::Error)]
pub enum ParseVectorError {
    #[error("bad counter pair {0:?} (want <hexid>:<value>)")]
    BadPair(String),
    #[error("bad hex id in pair {0:?}")]
    BadId(String),
    #[error("bad value in pair {0:?}")]
    BadValue(String),
}

impl std::str::FromStr for VersionVector {
    type Err = ParseVectorError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        if s.is_empty() {
            return Ok(VersionVector::default());
        }
        let mut counters = Vec::new();
        for pair in s.split(',') {
            let (id_str, val_str) = pair
                .split_once(':')
                .ok_or_else(|| ParseVectorError::BadPair(pair.to_string()))?;
            let id = u64::from_str_radix(id_str, 16)
                .map_err(|_| ParseVectorError::BadId(pair.to_string()))?;
            let value = val_str
                .parse::<u64>()
                .map_err(|_| ParseVectorError::BadValue(pair.to_string()))?;
            counters.push(Counter { id, value });
        }
        // Maintain the sort invariant even if the input was unsorted.
        counters.sort_by_key(|c| c.id);
        Ok(VersionVector { counters })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Two distinct node ids for tests (mirrors aio2 / mac).
    const AIO2: NodeId = 0x11;
    const MAC: NodeId = 0x22;

    fn vv(pairs: &[(NodeId, u64)]) -> VersionVector {
        let mut counters: Vec<Counter> = pairs.iter().map(|&(id, value)| Counter { id, value }).collect();
        counters.sort_by_key(|c| c.id);
        VersionVector { counters }
    }

    #[test]
    fn empty_vectors_are_equal() {
        let a = VersionVector::default();
        let b = VersionVector::default();
        assert_eq!(a.compare(&b), Ordering::Equal);
        assert!(a.is_empty());
    }

    #[test]
    fn update_is_monotonic_with_wallclock_floor() {
        // With now well above the counter, value tracks the wall clock.
        let v = VersionVector::default().update_with_now(AIO2, 1000);
        assert_eq!(v.counter(AIO2), 1000);
        let v = v.update_with_now(AIO2, 1000);
        // count+1 = 1001 > now(1000) → 1001
        assert_eq!(v.counter(AIO2), 1001);
        // A stale clock can never drag the value backwards.
        let v = v.update_with_now(AIO2, 5);
        assert_eq!(v.counter(AIO2), 1002);
    }

    #[test]
    fn update_keeps_counters_sorted_on_insert() {
        let v = VersionVector::default()
            .update_with_now(MAC, 10)
            .update_with_now(AIO2, 10); // smaller id inserted before MAC
        let ids: Vec<NodeId> = v.counters.iter().map(|c| c.id).collect();
        assert_eq!(ids, vec![AIO2, MAC]);
    }

    #[test]
    fn greater_and_lesser_are_symmetric() {
        let a = vv(&[(AIO2, 2), (MAC, 1)]);
        let b = vv(&[(AIO2, 1), (MAC, 1)]);
        assert_eq!(a.compare(&b), Ordering::Greater);
        assert_eq!(b.compare(&a), Ordering::Lesser);
        assert!(a.greater_equal(&b));
        assert!(b.lesser_equal(&a));
        assert!(!a.concurrent(&b));
    }

    #[test]
    fn missing_counter_on_one_side_is_greater_not_concurrent() {
        // a has a MAC counter b lacks, but a >= b on AIO2 too → clean Greater.
        let a = vv(&[(AIO2, 1), (MAC, 1)]);
        let b = vv(&[(AIO2, 1)]);
        assert_eq!(a.compare(&b), Ordering::Greater);
        assert_eq!(b.compare(&a), Ordering::Lesser);
        assert!(!a.concurrent(&b));
    }

    #[test]
    fn independent_advances_are_concurrent() {
        // aio2 advanced its own counter; mac advanced its own → conflict.
        let a = vv(&[(AIO2, 2), (MAC, 1)]);
        let b = vv(&[(AIO2, 1), (MAC, 2)]);
        assert!(a.concurrent(&b));
        assert!(b.concurrent(&a));
        assert_eq!(a.compare(&b), Ordering::ConcurrentGreater);
        assert_eq!(b.compare(&a), Ordering::ConcurrentLesser);
    }

    #[test]
    fn disjoint_node_writes_are_concurrent() {
        // Classic two-node offline edit of the *same key*: each only knows its
        // own counter. This is the conflict MS-2 must preserve.
        let a = vv(&[(AIO2, 1)]);
        let b = vv(&[(MAC, 1)]);
        assert!(a.concurrent(&b));
        assert!(b.concurrent(&a));
    }

    #[test]
    fn merge_takes_per_node_maxima() {
        let a = vv(&[(AIO2, 2), (MAC, 1)]);
        let b = vv(&[(AIO2, 1), (MAC, 3)]);
        let m = a.merge(&b);
        assert_eq!(m.counter(AIO2), 2);
        assert_eq!(m.counter(MAC), 3);
        // The merge dominates both inputs.
        assert!(m.greater_equal(&a));
        assert!(m.greater_equal(&b));
    }

    #[test]
    fn merge_unions_disjoint_nodes() {
        let a = vv(&[(AIO2, 1)]);
        let b = vv(&[(MAC, 1)]);
        let m = a.merge(&b);
        assert_eq!(m.counters.len(), 2);
        assert_eq!(m.counter(AIO2), 1);
        assert_eq!(m.counter(MAC), 1);
    }

    #[test]
    fn string_roundtrips() {
        let v = vv(&[(AIO2, 1700000000), (MAC, 42)]);
        let s = v.to_string();
        let back: VersionVector = s.parse().unwrap();
        assert_eq!(v, back);
    }

    #[test]
    fn empty_string_roundtrips_to_empty() {
        let v = VersionVector::default();
        assert_eq!(v.to_string(), "");
        let back: VersionVector = "".parse().unwrap();
        assert!(back.is_empty());
    }

    #[test]
    fn parse_sorts_unsorted_input() {
        // mac id (0x22) listed before aio2 id (0x11) → parser re-sorts.
        let back: VersionVector = "22:5,11:3".parse().unwrap();
        let ids: Vec<NodeId> = back.counters.iter().map(|c| c.id).collect();
        assert_eq!(ids, vec![AIO2, MAC]);
    }

    #[test]
    fn parse_rejects_garbage() {
        assert!("nopair".parse::<VersionVector>().is_err());
        assert!("zz:1".parse::<VersionVector>().is_err());
        assert!("11:notanum".parse::<VersionVector>().is_err());
    }

    #[test]
    fn node_id_from_name_is_stable_and_distinct() {
        assert_eq!(node_id_from_name("aio2"), node_id_from_name("aio2"));
        assert_ne!(node_id_from_name("aio2"), node_id_from_name("mac"));
        assert_ne!(node_id_from_name("aio2"), 0);
    }
}
