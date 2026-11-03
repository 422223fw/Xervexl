import struct, json, os
base = r'C:\\Users\\Anabel\\Documents\\Downloads\\Xervexl\\assets'
files = ['arena_music.wav','combat_geometry.json','fall.wav','menu_music.wav','steel.wav']
for f in files:
    path = os.path.join(base, f)
    if f.endswith('.wav'):
        with open(path, 'rb') as fh:
            header = fh.read(4)
        valid = header == b'RIFF'
    elif f.endswith('.json'):
        try:
            json.load(open(path))
            valid = True
        except:
            valid = False
    else:
        valid = False
    print(f'  {f}: {"VALID" if valid else "INVALID"}')