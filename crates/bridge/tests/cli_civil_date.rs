#[path = "../src/cli/civil_date.rs"]
mod civil_date;

mod baseline {
    include!("fixtures/civil_date_baseline.rs");

    pub fn compare(days: i64, actual: (i32, u32, u32)) {
        assert_eq!(actual, civil_from_days(days), "original civil: {days}");
        assert_eq!(actual, days_to_ymd(days), "original ymd: {days}");
    }
}

#[test]
fn references_are_exact_functions_from_the_pinned_source() {
    let mut command = std::process::Command::new("git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            command.env_remove(key);
        }
    }
    let result = command
        .args([
            "show",
            "69081c537ae3ce25647e49a29ca79f9fd093d2e3:crates/bridge/src/main.rs",
        ])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .output()
        .expect("read pinned source");
    assert!(result.status.success());
    let source = String::from_utf8(result.stdout).unwrap();
    let extract = |name: &str| {
        let start = source.find(&format!("fn {name}(")).unwrap();
        let end = start + source[start..].find("\n}").unwrap() + 2;
        &source[start..end]
    };
    assert_eq!(
        include_str!("fixtures/civil_date_baseline.rs"),
        format!(
            "{}\n\n{}\n",
            extract("civil_from_days"),
            extract("days_to_ymd")
        )
    );
}

#[test]
fn known_epoch_and_leap_century_dates() {
    for (days, expected) in [
        (0, (1970, 1, 1)),
        (-1, (1969, 12, 31)),
        (-25509, (1900, 2, 28)),
        (-25508, (1900, 3, 1)),
        (11016, (2000, 2, 29)),
        (11017, (2000, 3, 1)),
        (47540, (2100, 2, 28)),
        (47541, (2100, 3, 1)),
        (-719528, (0, 1, 1)),
        (-719529, (-1, 12, 31)),
    ] {
        assert_eq!(civil_date::from_days(days), expected, "day {days}");
    }
}

#[test]
fn two_full_eras_on_either_side_of_civil_origin_match_both_originals() {
    for days in (-719468 - 146097)..=(-719468 + 146097) {
        baseline::compare(days, civil_date::from_days(days));
    }
}

#[test]
fn reachable_seconds_domain_extremes_and_samples_match_both_originals() {
    for seconds in [
        i64::MIN,
        i64::MIN + 86400,
        -86401,
        -86400,
        -1,
        0,
        1,
        86399,
        86400,
        i64::MAX - 86400,
        i64::MAX,
    ] {
        let days = seconds.div_euclid(86400);
        baseline::compare(days, civil_date::from_days(days));
    }
    let mut state = 0x6a09e667f3bcc909_u64;
    for _ in 0..10000 {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        let days = (state as i64).div_euclid(86400);
        baseline::compare(days, civil_date::from_days(days));
    }
}
