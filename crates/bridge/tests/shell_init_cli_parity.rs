use std::process::{Command, Output};

const BASH_SNIPPET: &str = r#"# agent-bridge — OSC 133 shell integration (bash)
# See: docs/SHELL-INTEGRATION-OSC133.md
__ab_osc133_preexec() { printf '\e]133;C\a'; }
__ab_osc133_precmd() {
    local exit=$?
    printf '\e]133;D;%s\a\e]133;A\a' "$exit"
    PS1='\[\e]133;B\a\]'"${PS1_ORIG:-$PS1}"
    PS1_ORIG="${PS1_ORIG:-$PS1}"
}
trap '__ab_osc133_preexec' DEBUG
PROMPT_COMMAND="__ab_osc133_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
"#;

const ZSH_SNIPPET: &str = r#"# agent-bridge — OSC 133 shell integration (zsh)
# See: docs/SHELL-INTEGRATION-OSC133.md
__ab_osc133_preexec() { print -nP '\e]133;C\a'; }
__ab_osc133_precmd() {
    local exit=$?
    print -nP "\e]133;D;${exit}\a\e]133;A\a"
}
__ab_osc133_prompt_b() { print -nP '\e]133;B\a'; }
PS1='%{$(__ab_osc133_prompt_b)%}'"$PS1"
autoload -Uz add-zsh-hook
add-zsh-hook preexec __ab_osc133_preexec
add-zsh-hook precmd __ab_osc133_precmd
"#;

const FISH_SNIPPET: &str = r#"# agent-bridge — OSC 133 shell integration (fish)
# See: docs/SHELL-INTEGRATION-OSC133.md
function __ab_osc133_preexec --on-event fish_preexec
    printf '\e]133;C\a'
end
function __ab_osc133_postexec --on-event fish_postexec
    printf '\e]133;D;%s\a\e]133;A\a' $status
end
function fish_prompt_osc133 --description 'wrap fish_prompt with OSC 133 B marker'
    functions -c fish_prompt __ab_orig_fish_prompt 2>/dev/null
    function fish_prompt
        __ab_orig_fish_prompt
        printf '\e]133;B\a'
    end
end
fish_prompt_osc133
"#;

fn run_shell_init(args: &[&str]) -> Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command.arg("shell-init").args(args);
    for key in ["COLUMNS", "LINES", "CLICOLOR", "NO_COLOR"] {
        command.env_remove(key);
    }
    command.output().expect("run agent-bridge shell-init")
}

fn assert_success_without_stderr(output: &Output) {
    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stderr, b"");
}

#[test]
fn shell_init_bash_stdout_contract_is_exact() {
    let output = run_shell_init(&["bash"]);
    assert_success_without_stderr(&output);
    assert_eq!(output.stdout, BASH_SNIPPET.as_bytes());
}

#[test]
fn shell_init_zsh_stdout_contract_is_exact() {
    let output = run_shell_init(&["zsh"]);
    assert_success_without_stderr(&output);
    assert_eq!(output.stdout, ZSH_SNIPPET.as_bytes());
}

#[test]
fn shell_init_fish_stdout_contract_is_exact() {
    let output = run_shell_init(&["fish"]);
    assert_success_without_stderr(&output);
    assert_eq!(output.stdout, FISH_SNIPPET.as_bytes());
}

#[test]
fn shell_init_help_contract_is_exact() {
    let output = run_shell_init(&["--help"]);
    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 help output"),
        concat!(
            "Print an OSC 133 shell-integration snippet for the chosen shell to stdout. ",
            "Pipe into the matching rc file:\n\n",
            "agent-bridge shell-init bash >> ~/.bashrc agent-bridge shell-init zsh  >> ",
            "~/.zshrc agent-bridge shell-init fish >  ",
            "~/.config/fish/conf.d/agent-bridge-osc133.fish\n\n",
            "After re-sourcing the rc file (or starting a fresh shell), the PtyBackend's ",
            "`terminal_read_blocks` will return structured (command, output, exit_code, ",
            "start_ms, end_ms) tuples for every command run in agent-bridge-spawned panes. ",
            "See `docs/SHELL-INTEGRATION-OSC133.md` for protocol details.\n\n",
            "Usage: agent-bridge shell-init <SHELL>\n\n",
            "Arguments:\n",
            "  <SHELL>\n",
            "          Which shell flavour to emit a snippet for\n",
            "          \n",
            "          [possible values: bash, zsh, fish]\n\n",
            "Options:\n",
            "  -h, --help\n",
            "          Print help (see a summary with '-h')\n",
        )
    );
}

#[test]
fn shell_init_invalid_shell_contract_is_exact() {
    let output = run_shell_init(&["powershell"]);
    assert_eq!(output.status.code(), Some(2));
    assert_eq!(output.stdout, b"");
    assert_eq!(
        String::from_utf8(output.stderr).expect("utf-8 error output"),
        concat!(
            "error: invalid value 'powershell' for '<SHELL>'\n",
            "  [possible values: bash, zsh, fish]\n\n",
            "For more information, try '--help'.\n",
        )
    );
}
