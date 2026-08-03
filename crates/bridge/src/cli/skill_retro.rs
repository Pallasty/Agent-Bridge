use ab_store::MemoryRecord;

#[derive(Debug, serde::Serialize)]
pub(crate) struct SkillRetroLessonRow {
    pub(crate) key: String,
    pub(crate) created_at: i64,
    pub(crate) last_accessed_at: i64,
    pub(crate) access_count: u64,
    pub(crate) importance: f64,
    pub(crate) consulted: bool,
}

#[derive(Debug, serde::Serialize)]
pub(crate) struct SkillRetroReport {
    pub(crate) window_days: u32,
    pub(crate) cutoff_unix: i64,
    pub(crate) now_unix: i64,
    pub(crate) lessons_total: usize,
    pub(crate) lessons_consulted: usize,
    pub(crate) consulted_ratio: f64,
    pub(crate) mean_access_count: f64,
    pub(crate) rows: Vec<SkillRetroLessonRow>,
}

/// Pure aggregator for the authority-bearing SkillRetro executor. `now` and
/// `cutoff` are caller-injected for deterministic testing.
pub(crate) fn aggregate_skill_retro(
    lessons: Vec<MemoryRecord>,
    window_days: u32,
    now: i64,
    cutoff: i64,
) -> SkillRetroReport {
    let mut rows: Vec<SkillRetroLessonRow> = lessons
        .into_iter()
        .map(|m| SkillRetroLessonRow {
            consulted: m.access_count > 0,
            key: m.key,
            created_at: m.created_at,
            last_accessed_at: m.last_accessed_at,
            access_count: m.access_count,
            importance: m.importance,
        })
        .collect();
    // Order by access_count DESC (most-consulted first) for readable
    // text output; JSON consumers can re-sort.
    rows.sort_by(|a, b| b.access_count.cmp(&a.access_count));
    let total = rows.len();
    let consulted = rows.iter().filter(|r| r.consulted).count();
    let mean_access = if total == 0 {
        0.0
    } else {
        rows.iter().map(|r| r.access_count as f64).sum::<f64>() / total as f64
    };
    let consulted_ratio = if total == 0 {
        0.0
    } else {
        consulted as f64 / total as f64
    };
    SkillRetroReport {
        window_days,
        cutoff_unix: cutoff,
        now_unix: now,
        lessons_total: total,
        lessons_consulted: consulted,
        consulted_ratio,
        mean_access_count: mean_access,
        rows,
    }
}
