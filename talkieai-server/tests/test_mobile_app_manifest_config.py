import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_android_record_audio_permission_supports_current_sdk_versions():
    manifest = (ROOT / "talkieai-uniapp/src/manifest.json").read_text(encoding="utf-8")
    match = re.search(
        r'<uses-permission android:name=\\"android\.permission\.RECORD_AUDIO\\"([^>]*)/>',
        manifest,
    )

    assert match, "Android RECORD_AUDIO permission must be declared"
    assert "maxSdkVersion" not in match.group(1)
