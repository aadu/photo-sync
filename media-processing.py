from pathlib import Path
import os
import time
from typing import Iterable
import win32api
import subprocess
from pandas import DataFrame, merge, Series
import shutil

SOURCE_DIR = 'E:/media/'
TARGET_DIR = 'E:/odrive/Amazon Cloud Drive/media/'


def microsoft_photos_pids():
    processes = subprocess.check_output('tasklist')
    return [p.split()[1] for p in str(processes).split(r'\r\n') if 'Microsoft.Photos.exe' in p]


def kill_photos():
    PROCESS_TERMINATE = 1
    for pid in microsoft_photos_pids():
        handle = win32api.OpenProcess(PROCESS_TERMINATE, False, int(pid))
        win32api.TerminateProcess(handle, -1)
        win32api.CloseHandle(handle)


def list_files(path: str) -> Iterable[str]:
    files = []
    for entry in os.scandir(str(Path(path))):
        if entry.is_dir():
            files += list_files(entry.path)
        else:
            files.append(entry.path)
    return files


def file_stub_df(path: str) -> DataFrame:
    path = str(Path(path))
    file_list = list_files(path)
    df = DataFrame({'path': file_list})
    df['filename'] = df.path.map(lambda s: s.replace(
        path, '')[1:].replace('.cloudf', '').replace('.cloud', ''))
    return df


def source_vs_target_df(source_path: str, target_path: str) -> DataFrame:
    src = file_stub_df(source_path)
    src.columns = ['src_path', 'filename']
    des = file_stub_df(target_path)
    des.columns = ['target_path', 'filename']
    return merge(src, des, on='filename', how='outer')


def missing_files() -> DataFrame:    
    df = source_vs_target_df(SOURCE_DIR, TARGET_DIR)
    return df.ix[df.target_path.isnull(), 'filename'].reset_index(drop=True)
    

def mts_files() -> DataFrame:
    df = source_vs_target_df(SOURCE_DIR, TARGET_DIR)
    df = df[df.filename.str.contains(r'(?i)\.mts$')]
    df['filename'] = df.filename.str.extract(r'([^.]*)', expand=False)
    return df

def mp4_files() -> DataFrame:
    df = source_vs_target_df(SOURCE_DIR, TARGET_DIR)
    df = df[df.filename.str.contains(r'(?i)\.mp4$')]
    df['filename'] = df.filename.str.extract(r'([^.]*)', expand=False)
    return df

def non_converted_files() -> Iterable[str]:
    mts = mts_files()
    mp4 = mp4_files()
    files = mts[~mts.filename.isin(mp4.filename)].src_path.tolist()
    return [f.replace('\\', '/') for f in files]


def deleted_files() -> DataFrame:    
    df = source_vs_target_df(SOURCE_DIR, TARGET_DIR)
    return df.ix[df.src_path.isnull(), 'filename'].reset_index(drop=True)


def delete_files():
    deleted = deleted_files()
    for f in deleted:
        dst = os.path.join(str(Path(TARGET_DIR)), f)
        print('Deleting {}'.format(dst))
        try:
            os.remove(dst)
        except Exception as e:
            print(str(e))
  

def copy_missing() -> None:
    missing = missing_files()
    for f in missing:
        src = os.path.join(str(Path(SOURCE_DIR)), f)
        dst = os.path.join(str(Path(TARGET_DIR)), f)
        print('Moving {} to {}'.format(src, dst))
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)                    
            shutil.copy2(src, dst)
        except Exception as e:
            print(str(e))
    

def non_synced_files(subdirectory: str) -> Series:
    files = list_files(TARGET_DIR + subdirectory)
    s = Series(files)
    return s[s.str.contains('[.]cloudf?$')]

   
def sync_files(files: Iterable[str]) -> None:
    for i, f in enumerate(files):
        print('{}/{}: {}'.format(i, len(files), f))
        os.startfile(f)
        time.sleep(.5)
        if i % 10 == 0:
            kill_photos()
        
        
def sync_non_synced(subdirectory='') -> None:
    files = non_synced_files(subdirectory)
    sync_files(files)

# meta_cmd = (
#     'ffmpeg',
#     '-i', '{original}'.format(original=src),
#     '-i', '{mp4}'.format(mp4=tmp),
#     '-map', '1',
#     '-map_metadata', '0',
#     '-c', 'copy', '{dst}'.format(dst=tmp+'.fixed.mp4'),
# )



def get_info(file_path):
    info_cmd = """
    exiftool -a -s -time:all {dst}
    """.format(dst=file_path)
    results = subprocess.check_output(info_cmd.format(dst=dst).split())
    return results.decode()


def get_tags(file_path):
    results = get_info(file_path).split('\n')
    tags = [r.split()[0] for r in results if r.split()]
    return tags


def get_create_time(file_path):
    src_info = get_info(file_path).split('\n')
    return ' '.join([r.split()[2:] for r in src_info if r.startswith('DateTimeOriginal')][0])


def copy_meta_data(src, dst):
    tags = get_tags(dst)
    create_time = get_create_time(src)
    for tag in tags:
        cmd = """exiftool -{tag}="{date}" -overwrite_original {f}""".format(tag=tag, date=create_time, f=dst)
        subprocess.run(cmd)
    stinfo = os.stat(src)
    stinfo.st_atime
    os.utime(dst, (stinfo.st_atime, stinfo.st_mtime))
    print(get_info(dst))
    

def convert_to_mp4(src):
    print("Processing {}".format(src))
    dst = src[:-3] + 'mp4'
    cmd = (
        'C:/Program Files/Handbrake/HandBrakeCLI.exe',
        '-i', '{src}'.format(src=src),
        '-o', '{dst}'.format(dst=dst),
        '-Z', 'High Profile',
    )
    subprocess.run(cmd)
    copy_meta_data(src, dst)
