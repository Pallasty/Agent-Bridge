#![cfg(unix)]

use std::os::{
    fd::OwnedFd,
    unix::{net::UnixStream, process::ExitStatusExt},
};
use std::process::{Command, Stdio};

#[test]
fn cli_exits_by_sigpipe_when_stdout_consumer_is_closed() {
    let (reader, writer) = UnixStream::pair().expect("create stdout socket pair");
    drop(reader);
    let writer: OwnedFd = writer.into();

    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args(["shell-init", "bash"])
        .stdout(Stdio::from(writer))
        .output()
        .expect("run agent-bridge shell-init");

    assert_eq!(output.status.signal(), Some(libc::SIGPIPE));
    assert!(
        !String::from_utf8_lossy(&output.stderr).contains("Broken pipe"),
        "closed stdout must not print a broken-pipe panic: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}
