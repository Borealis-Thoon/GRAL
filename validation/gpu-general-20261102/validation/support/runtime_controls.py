"""Verbatim helper definitions from the prior reviewed synthetic harness."""
import argparse


import datetime


import ctypes


import json


import os


import re


import shutil


import threading


import time


import struct


import zipfile


from pathlib import Path


def validate_affinity_records(records, model_pid, expected_mask, mode):
    parents = {row['pid']: row['ppid'] for row in records}
    if not any(row['pid'] == model_pid for row in records):
        raise ValueError('model runtime affinity not observed')
    observed = []
    gpu_python = False
    for row in records:
        pid = row['pid']
        ancestor = pid
        while ancestor in parents and ancestor != model_pid:
            ancestor = parents[ancestor]
        if ancestor != model_pid:
            continue
        if row['mask'] != expected_mask:
            raise ValueError('model-tree runtime affinity mask mismatch')
        observed.append(pid)
        gpu_python |= pid != model_pid and row['name'].lower().startswith('python')
    if mode == 'gpu' and not gpu_python:
        raise ValueError('GPU Python child affinity not observed')
    return {'verified': True, 'verification_scope': 'startup_mask_exact_before_resume; runtime_mask_sampled_about_1s',
            'observed_pids': sorted(set(observed)),
            'gpu_python_observed': gpu_python}


def runtime_setting(name):
    upper = name.upper()
    if upper.startswith('DOTNET_'):
        return upper[7:]
    if upper.startswith('COMPLUS_'):
        return upper[8:]
    return ''


def compilation_setting(name):
    setting = runtime_setting(name)
    return setting.startswith(('TIERED', 'TC_', 'JIT', 'READYTORUN', 'ZAP', 'NGEN'))


def runtime_tuning_setting(name):
    setting = runtime_setting(name)
    if any(word in setting for word in ('SECRET', 'TOKEN', 'PASSWORD', 'KEY', 'CONNECTION')):
        return False
    return setting in ('TIEREDCOMPILATION', 'TIEREDPGO', 'TC_QUICKJIT', 'TC_QUICKJITFORLOOPS',
                       'TC_ONSTACKREPLACEMENT', 'READYTORUN', 'PROCESSORCOUNT', 'PROCCOUNT',
                       'GCSERVER', 'GCCONCURRENT', 'GCHEAPHARDLIMIT', 'GCHEAPHARDLIMITPERCENT',
                       'GCDYNAMICADAPTATIONMODE', 'ENABLEDIAGNOSTICS', 'ENABLE_PROFILING')


def configure_tiering(environment, tiering):
    if tiering not in ('default', 'on', 'off'):
        raise ValueError('invalid tiering choice')
    removed = {key: value for key, value in environment.items() if compilation_setting(key)}
    startup = [key for key in environment if runtime_setting(key) == 'STARTUP_HOOKS']
    child = {key: value for key, value in environment.items() if key not in removed and key not in startup}
    if tiering != 'default':
        child['DOTNET_TieredCompilation'] = '1' if tiering == 'on' else '0'
    return child, {'requested_tiering': tiering,
                   'removed_inherited_compilation': sorted(removed),
                   'removed_inherited_startup_hooks': sorted(startup),
                   'child_runtime_environment': {key: value if re.fullmatch(r'(?:-?\d+|0x[0-9a-fA-F]+|true|false)', value, re.I) else '<redacted>'
                                                 for key, value in child.items()
                                                 if runtime_tuning_setting(key)},
                   'other_prefixed_environment_keys': sorted(key for key in child
                       if runtime_setting(key) and not runtime_tuning_setting(key))}

