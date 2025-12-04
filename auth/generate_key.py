# auth/generate_key.py
import secrets
import os

def generate_api_key(length=32):
    return secrets.token_hex(length//2)

def add_key_to_env(key, env_file=".env"):
    if not os.path.exists(env_file):
        with open(env_file, "w") as f:
            f.write(f"API_KEYS={key}\n")
        print("Created .env and added key.")
        return

    lines = open(env_file).read().splitlines()
    new_lines = []
    found = False

    for line in lines:
        if line.startswith("API_KEYS="):
            found = True
            existing = line.split("=", 1)[1]
            keys = [k.strip() for k in existing.split(",") if k.strip()]
            keys.append(key)
            new_lines.append("API_KEYS=" + ",".join(keys))
        else:
            new_lines.append(line)

    if not found:
        new_lines.append("API_KEYS=" + key)

    with open(env_file, "w") as f:
        f.write("\n".join(new_lines))

    print("API key added to .env")

if __name__ == "__main__":
    k = generate_api_key()
    add_key_to_env(k)
    print("New API key:", k)
