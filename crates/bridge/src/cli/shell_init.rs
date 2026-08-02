use crate::ShellKind;

/// OSC 133 shell-integration snippets. Source-of-truth lives here; the
/// human-readable copy in `docs/SHELL-INTEGRATION-OSC133.md` is intended
/// to track this verbatim. If you edit one, mirror the change in the doc
/// (or vice-versa) so the install instructions stay consistent.
pub(crate) fn shell_init_snippet(shell: ShellKind) -> &'static str {
    match shell {
        ShellKind::Bash => {
            "\
# agent-bridge — OSC 133 shell integration (bash)
# See: docs/SHELL-INTEGRATION-OSC133.md
__ab_osc133_preexec() { printf '\\e]133;C\\a'; }
__ab_osc133_precmd() {
    local exit=$?
    printf '\\e]133;D;%s\\a\\e]133;A\\a' \"$exit\"
    PS1='\\[\\e]133;B\\a\\]'\"${PS1_ORIG:-$PS1}\"
    PS1_ORIG=\"${PS1_ORIG:-$PS1}\"
}
trap '__ab_osc133_preexec' DEBUG
PROMPT_COMMAND=\"__ab_osc133_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}\"
"
        }
        ShellKind::Zsh => {
            "\
# agent-bridge — OSC 133 shell integration (zsh)
# See: docs/SHELL-INTEGRATION-OSC133.md
__ab_osc133_preexec() { print -nP '\\e]133;C\\a'; }
__ab_osc133_precmd() {
    local exit=$?
    print -nP \"\\e]133;D;${exit}\\a\\e]133;A\\a\"
}
__ab_osc133_prompt_b() { print -nP '\\e]133;B\\a'; }
PS1='%{$(__ab_osc133_prompt_b)%}'\"$PS1\"
autoload -Uz add-zsh-hook
add-zsh-hook preexec __ab_osc133_preexec
add-zsh-hook precmd __ab_osc133_precmd
"
        }
        ShellKind::Fish => {
            "\
# agent-bridge — OSC 133 shell integration (fish)
# See: docs/SHELL-INTEGRATION-OSC133.md
function __ab_osc133_preexec --on-event fish_preexec
    printf '\\e]133;C\\a'
end
function __ab_osc133_postexec --on-event fish_postexec
    printf '\\e]133;D;%s\\a\\e]133;A\\a' $status
end
function fish_prompt_osc133 --description 'wrap fish_prompt with OSC 133 B marker'
    functions -c fish_prompt __ab_orig_fish_prompt 2>/dev/null
    function fish_prompt
        __ab_orig_fish_prompt
        printf '\\e]133;B\\a'
    end
end
fish_prompt_osc133
"
        }
    }
}
