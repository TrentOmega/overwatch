import subprocess


def publish(files, topic_config, date_str, auto_push=False):
    """Git add, commit, and optionally push the generated brief files."""
    slug = topic_config["slug"]
    name = topic_config["name"]

    for f in files:
        subprocess.run(["git", "add", f], check=True)

    message = f"brief: {name} {date_str}"
    subprocess.run(["git", "commit", "-m", message], check=True)
    print(f"  Committed: {message}")

    if auto_push:
        subprocess.run(["git", "push"], check=True)
        print("  Pushed to remote")
