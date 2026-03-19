import requests


if __name__ == "__main__":
    # TODO(next step): call POST /tts with text and save returned wav.
    resp = requests.get("http://127.0.0.1:8000/health", timeout=10)
    print(resp.json())
