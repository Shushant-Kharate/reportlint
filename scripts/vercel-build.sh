#!/usr/bin/env bash
set -euo pipefail
export CI=true
export FLUTTER_SUPPRESS_ANALYTICS=true
FLUTTER_VERSION=3.47.6
SDK_DIR="${VERCEL_CACHE_DIR:-/tmp}/reportlint-flutter-${FLUTTER_VERSION}"
if [ ! -x "$SDK_DIR/flutter/bin/flutter" ]; then
  mkdir -p "$SDK_DIR"
  python - "$FLUTTER_VERSION" "$SDK_DIR" <<'PY'
import hashlib,json,pathlib,sys,tarfile,urllib.request
version,folder=sys.argv[1],pathlib.Path(sys.argv[2])
index=json.load(urllib.request.urlopen('https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json'))
release=next(r for r in index['releases'] if r['version']==version and r['channel']=='stable' and r.get('dart_sdk_arch','x64')=='x64')
archive=folder/'sdk.tar.xz'
urllib.request.urlretrieve(index['base_url']+'/'+release['archive'],archive)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==release['sha256'], 'Flutter SDK checksum mismatch'
with tarfile.open(archive) as src:
    src.extractall(folder,filter='data')
archive.unlink()
PY
fi
export PATH="$SDK_DIR/flutter/bin:$PATH"
git config --global --add safe.directory "$SDK_DIR/flutter"
flutter config --no-analytics
cd frontend
flutter pub get
flutter build web --release --base-href /app/ --no-web-resources-cdn --dart-define=MAX_UPLOAD_MB=4
