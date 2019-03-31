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


def missing_files(filter: str = None) -> DataFrame:    
    df = source_vs_target_df(SOURCE_DIR, TARGET_DIR)
    missing = df.ix[df.target_path.isnull(), 'filename'].reset_index(drop=True)
    if filter:
        missing = missing[~missing.str.contains(filter)]
    return missing

def copy_missing(filter: str = None) -> None:
    missing = missing_files(filter)
    for f in missing:
        src = os.path.join(str(Path(SOURCE_DIR)), f)
        dst = os.path.join(str(Path(TARGET_DIR)), f).lower()
        print('Moving {} to {}'.format(src, dst))
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)                    
            shutil.copy2(src, dst)
        except Exception as e:
            print(str(e))
    
def non_synced_files(subdirectory: str = '') -> Series:
    files = list_files(TARGET_DIR + subdirectory)
    s = Series(files)
    return s[s.str.contains('[.]cloudf?$')]

   
def sync_files(files: Iterable[str]) -> None:
    for i, f in enumerate(files):
        print('{}/{}: {}'.format(i, len(files), f))
        os.startfile(f)
        time.sleep(2)
        if i % 2 == 0:
            kill_photos()
        
        
def sync_non_synced(subdirectory: str = '') -> None:
    files = non_synced_files(subdirectory)
    sync_files(files)
    