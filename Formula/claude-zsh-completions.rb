class ClaudeZshCompletions < Formula
  desc "Zsh tab-completions for the Claude Code CLI"
  homepage "https://github.com/ivanearisty/claude-zsh-completions"
  url "https://github.com/ivanearisty/claude-zsh-completions/archive/refs/tags/v2.1.138.tar.gz"
  sha256 "8476044c02a6f8e2418eee29312f635dcfec42438cf4fe9c2f3ec732b9a0eba0"
  license "MIT"
  head "https://github.com/ivanearisty/claude-zsh-completions.git", branch: "main"

  # url/sha256 above are bumped by tools/update-formula.sh on each tagged release.

  def install
    zsh_completion.install "_claude"
  end

  def caveats
    <<~EOS
      Make sure Homebrew's completions are on your fpath, then rebuild the cache:

        autoload -Uz compinit && compinit

      Optional but recommended (lets `claude --resume <TAB>` cache session lookups):

        zstyle ':completion:*' use-cache on
    EOS
  end

  test do
    assert_path_exists zsh_completion/"_claude"
    system "zsh", "-n", zsh_completion/"_claude"
  end
end
