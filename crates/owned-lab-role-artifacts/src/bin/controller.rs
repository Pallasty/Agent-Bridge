#![forbid(unsafe_code)]

fn main() -> std::process::ExitCode {
    ab_owned_lab_role_artifacts::run(
        ab_owned_lab_role_artifacts::Role::Controller,
        std::env::args_os().skip(1),
    )
}
