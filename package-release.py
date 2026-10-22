"""Package public game runtime plus corresponding source; never include private data."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PUBLIC_DIRS=('src','vendor','shaders','assets','tests','third_party','oreon-bridge','runtime')
PUBLIC_FILES=('LICENSE','THIRD_PARTY.md','OREON-INTEGRATION.md','README.md','SCORING.md','VALIDATION.md','WORKSHOP.md','accounts.example.json','package.ps1','project.json',
              'server.py','rules.py','combat.py','hitboxes.py','arena_features.py','game_modes.py','bot_brain.py','bot_learning.py','realms.py','social.py','voxel_world.py',
              'session_store.py','start.ps1','build.ps1','build-oreon.ps1','setup-oreon.py','package-release.py','Play-Xervexl.cmd')
BUILD_TOOLS=('tools/make_audio.py','tools/make_shaders.py','tools/export_combat_geometry.cpp')

def main():
    files=[ROOT/p for p in PUBLIC_FILES+BUILD_TOOLS+('build/Xervexl.exe',)]
    # Every root Python module is part of the authoritative server/build source.
    files+=list(ROOT.glob('*.py'))
    for directory in PUBLIC_DIRS:
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and not {'target','__pycache__','.git'}.intersection(p.relative_to(ROOT).parts))
    files=sorted(set(files))
    if not (ROOT/'runtime/oreon/xervexl-oreon.jar').exists():raise RuntimeError('Build Oreon first')
    if not (ROOT/'runtime/sources/OpenJDK8U-jdk-sources_8u504b01.tar.gz').exists():raise RuntimeError('Run setup-oreon.py to include Java corresponding source')
    missing=[str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    if missing:raise RuntimeError('Missing public source: '+', '.join(missing))
    archive=ROOT/'build/Xervexl-Windows.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in files:
            relative=path.relative_to(ROOT)
            if {'data','.git'}.intersection(relative.parts):raise RuntimeError('Private file in package')
            output.write(path,relative.as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT/'build/Xervexl-Windows.zip.sha256').write_text(digest+'  Xervexl-Windows.zip\n','utf-8')
    print(json.dumps(dict(archive=str(archive),files=len(files),bytes=archive.stat().st_size,sha256=digest)))

if __name__=='__main__':main()
