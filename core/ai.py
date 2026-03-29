import copy
import os
import shlex
import subprocess
import tempfile


DEFAULT_PROVIDER_CONFIGS = {
    "claude": {
        "command": ["claude", "-p", "-"],
        "model_flag": "--model",
        "strip_env": ["CLAUDECODE"],
        "working_dir": "/tmp",
        "output_mode": "stdout",
    },
    "codex": {
        "command": [
            "codex",
            "--search",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-",
        ],
        "model_flag": "--model",
        "strip_env": [],
        "working_dir": "/tmp",
        "output_mode": "file",
        "output_file_flag": "--output-last-message",
    },
}


def resolve_ai_settings(global_config, provider_override=None, model_override=None):
    """Resolve AI settings from CLI overrides, env vars, and config."""
    ai_config = global_config.get("ai", {})

    provider = provider_override or os.getenv("OVERWATCH_AI_PROVIDER") or ai_config.get("provider") or "codex"
    model = model_override or os.getenv("OVERWATCH_AI_MODEL") or os.getenv("OVERWATCH_MODEL") or ai_config.get("model")
    timeout = int(os.getenv("OVERWATCH_AI_TIMEOUT") or ai_config.get("timeout_seconds", 600))

    providers = copy.deepcopy(DEFAULT_PROVIDER_CONFIGS)
    for name, overrides in (ai_config.get("providers") or {}).items():
        providers[name] = {**providers.get(name, {}), **(overrides or {})}

    if provider not in providers:
        available = ", ".join(sorted(providers))
        raise ValueError(f"Unknown AI provider '{provider}'. Configure it under ai.providers or use one of: {available}")

    settings = copy.deepcopy(providers[provider])

    command_override = os.getenv("OVERWATCH_AI_COMMAND")
    if command_override:
        settings["command"] = shlex.split(command_override)

    if not settings.get("command"):
        raise ValueError(f"AI provider '{provider}' has no command configured")

    settings["provider"] = provider
    settings["model"] = model
    settings["timeout_seconds"] = timeout
    settings["working_dir"] = settings.get("working_dir") or ai_config.get("working_dir") or "/tmp"
    settings["strip_env"] = settings.get("strip_env", [])
    settings["output_mode"] = settings.get("output_mode", "stdout")

    return settings


def run_prompt(prompt, ai_settings):
    """Run a prompt through the configured AI CLI."""
    cmd = list(ai_settings["command"])
    stdin_arg = cmd.pop() if cmd and cmd[-1] == "-" else None
    model = ai_settings.get("model")
    model_flag = ai_settings.get("model_flag")
    output_mode = ai_settings.get("output_mode", "stdout")
    output_path = None

    if model and model_flag:
        cmd.extend([model_flag, model])

    if output_mode == "file":
        output_file_flag = ai_settings.get("output_file_flag")
        if not output_file_flag:
            raise ValueError(f"AI provider '{ai_settings['provider']}' requires output_file_flag for file mode")
        with tempfile.NamedTemporaryFile(prefix="overwatch-ai-", suffix=".txt", delete=False) as handle:
            output_path = handle.name
        cmd.extend([output_file_flag, output_path])

    if stdin_arg:
        cmd.append(stdin_arg)

    env = {k: v for k, v in os.environ.items() if k not in set(ai_settings.get("strip_env", []))}
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=ai_settings.get("timeout_seconds", 600),
        env=env,
        cwd=ai_settings.get("working_dir", "/tmp"),
    )

    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{ai_settings['provider']} CLI failed: {stderr[:500]}")

    if output_mode == "file":
        try:
            with open(output_path) as f:
                content = f.read().strip()
        finally:
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)
        if content:
            return content

    return (result.stdout or "").strip()
