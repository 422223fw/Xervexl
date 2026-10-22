"""Download a portable, verified Java 8/Maven toolchain. No admin installation.
Run from the repository root: python setup-oreon.py
The Java corresponding-source archive is also bundled with binary releases.
"""
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TOOLS=ROOT/'build/java-tools'
JAVA_RELEASE='https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u504-b01/'
JDK='OpenJDK8U-jdk_x64_windows_hotspot_8u504b01.zip'
SOURCES='OpenJDK8U-jdk-sources_8u504b01.tar.gz'
MAVEN='https://archive.apache.org/dist/maven/maven-3/3.9.11/binaries/apache-maven-3.9.11-bin.zip'

def read(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Xervexl-build/0.12'}),timeout=120) as response:return response.read()

def download(url,path,algorithm,expected):
    expected=expected.split()[0].lower();path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or hashlib.new(algorithm,path.read_bytes()).hexdigest()!=expected:
        temporary=path.with_suffix(path.suffix+'.download')
        temporary.write_bytes(read(url))
        if hashlib.new(algorithm,temporary.read_bytes()).hexdigest()!=expected:raise RuntimeError('Checksum mismatch: '+url)
        temporary.replace(path)
    print('Verified '+path.name,flush=True)
    return expected

def unpack(path,directory):
    directory.mkdir(parents=True,exist_ok=True);base=directory.resolve()
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            target=(base/entry.filename).resolve()
            if not target.is_relative_to(base):raise ValueError('Archive entry escapes portable toolchain')
        archive.extractall(directory)

def main():
    TOOLS.mkdir(parents=True,exist_ok=True)
    jdk_hash=download(JAVA_RELEASE+JDK,TOOLS/'jdk8.zip','sha256',read(JAVA_RELEASE+JDK+'.sha256.txt').decode())
    maven_hash=download(MAVEN,TOOLS/'maven.zip','sha512',read(MAVEN+'.sha512').decode())
    source_hash=download(JAVA_RELEASE+SOURCES,ROOT/'runtime/sources'/SOURCES,'sha256',read(JAVA_RELEASE+SOURCES+'.sha256.txt').decode())
    if not (TOOLS/'jdk/jdk8u504-b01/bin/javac.exe').exists():unpack(TOOLS/'jdk8.zip',TOOLS/'jdk')
    if not (TOOLS/'maven/apache-maven-3.9.11/bin/mvn.cmd').exists():unpack(TOOLS/'maven.zip',TOOLS/'maven')
    config=dict(java_home=str(TOOLS/'jdk/jdk8u504-b01'),maven=str(TOOLS/'maven/apache-maven-3.9.11/bin/mvn.cmd'))
    (TOOLS/'toolchain.json').write_text(json.dumps(config,indent=2),'utf-8')
    (TOOLS/'settings.xml').write_text('<settings><mirrors><mirror><id>central-tls</id><mirrorOf>*</mirrorOf><url>https://repo1.maven.org/maven2</url></mirror></mirrors></settings>','utf-8')
    (ROOT/'runtime/sources/manifest.json').write_text(json.dumps(dict(java_source_url=JAVA_RELEASE+SOURCES,java_source_sha256=source_hash,jdk_sha256=jdk_hash,maven_sha512=maven_hash),indent=2),'utf-8')
    print('Ready. Run build-oreon.ps1, then build.ps1 with your C++ compiler path.')

if __name__=='__main__':main()
