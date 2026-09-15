# Opt-in zsh hardening for frappe_docker operators.
#
# Source this file from an interactive zsh session:
#
#   source scripts/enable-zsh-hardening.zsh
#
# Effect: commands typed with a leading space are excluded from shell
# history (HIST_IGNORE_SPACE). Get into the habit of prefixing any command
# that handles a secret with a space so an accidental paste never lands in
# ~/.zsh_history.
#
# LIMITATIONS -- read before relying on this:
# - This protects shell history ONLY. bench writes its full argv, including
#   any password passed as a CLI argument, into bench.log regardless of this
#   setting. Never pass passwords as bench CLI arguments (omit the flag so
#   bench prompts securely via getpass instead).
# - Enabling it requires actually running `setopt HIST_IGNORE_SPACE` (or
#   sourcing this file) in each already-open shell session; sourcing .zshrc
#   alone in an open session may not retroactively apply it.
setopt HIST_IGNORE_SPACE
